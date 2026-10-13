"""Análise de ISO e de executável (ELF) — sem executar nada do conteúdo."""
from __future__ import annotations

import hashlib
from collections import Counter
from dataclasses import dataclass, field
from typing import Callable, Dict, List, Optional

from .elf import Elf, ElfError, STT_FUNC, parse_elf
from .formats import identify
from .iso9660 import IsoImage, IsoError, parse_system_cnf
from .mips import Instr, decode
from .translator import ASSUMPTIONS, FuncResult, translate_function

HW_REGIONS = {
    0x1000: "Registradores de I/O do EE (timers, IPU, GIF, VIF, DMA…)",
    0x1001: "Registradores de I/O do EE (DMA/controle)",
    0x1100: "Memórias das unidades vetoriais (VU0/VU1)",
    0x1200: "Registradores privilegiados do Graphics Synthesizer (GS)",
    0x1c00: "RAM do IOP",
    0x1f80: "I/O do IOP/SIF (varia por dispositivo)",
    0x1fc0: "ROM da BIOS",
    0x7000: "Scratchpad do EE (16 KB)",
}

ProgressCb = Callable[[str, int], None]


def _noop(stage: str, pct: int) -> None:
    pass


@dataclass
class ElfAnalysis:
    entry: int
    kind: str
    looks_like_ee: bool
    sha256: str
    size: int
    segments: List[dict]
    sections: List[dict]
    n_symbols: int
    n_instructions: int
    categories: Dict[str, int]
    mnemonics_top: Dict[str, int]
    ps2_specific: Dict[str, int]
    unknown_words: int
    functions: List[FuncResult]
    hardware_refs: List[dict]
    syscalls: List[dict]
    unsupported_summary: Dict[str, int]
    translated_pct: float
    port_level: int
    port_label: str
    port_notes: List[str]
    assumptions: List[str] = field(default_factory=lambda: list(ASSUMPTIONS))

    def to_dict(self) -> dict:
        d = {k: v for k, v in self.__dict__.items() if k != "functions"}
        d["entry"] = f"0x{self.entry:08x}"
        d["functions"] = [f.to_dict() for f in self.functions]
        d["functions_total"] = len(self.functions)
        return d


def _scan_text(elf: Elf):
    """Decodifica todas as palavras dos segmentos executáveis. Pode incluir dados embutidos."""
    for seg in elf.exec_segments():
        for off in range(0, seg.filesz - 3, 4):
            w = int.from_bytes(elf.data[seg.offset + off: seg.offset + off + 4], "little")
            yield decode(w, seg.vaddr + off)


def port_status(funcs: List[FuncResult], hw_refs: list, adapters_ready: bool = False):
    """Classificação honesta. Nível 3 (port nativo) só com TUDO traduzido + adaptadores reais."""
    total = len(funcs)
    ok = sum(1 for f in funcs if f.status == "translated")
    notes: List[str] = []
    if total == 0:
        return 0, "Apenas analisado (nenhuma função traduzida)", ["Nenhuma função encontrada."]
    if hw_refs:
        notes.append(f"{len(hw_refs)} referência(s) a hardware do PS2 exigem reimplementação "
                     "(GS/VU/DMA/IOP) que NÃO existe neste protótipo.")
    if ok == 0:
        level, label = 0, "Apenas analisado (nenhuma função traduzida)"
    elif ok < total:
        level, label = 1, f"Tradução parcial de código ({ok}/{total} funções)"
    else:
        level, label = 2, "Todo o código descoberto traduzido para C — ainda SEM runtime de hardware"
    if level == 2 and adapters_ready and not hw_refs:
        level, label = 3, "Candidato a port nativo (requer validação em execução)"
    if level < 3:
        notes.append("Resultado NÃO é um port nativo completo. Não há GS, VU, áudio, kernel/BIOS "
                     "nem IOP implementados; nada foi executado/validado com o jogo real.")
    return level, label, notes


def analyze_elf(data: bytes, progress: ProgressCb = _noop) -> ElfAnalysis:
    elf = parse_elf(data)
    progress("Lendo cabeçalhos ELF", 5)
    segs = [{"type": s.type, "vaddr": f"0x{s.vaddr:08x}", "filesz": s.filesz, "memsz": s.memsz,
             "flags": ("R" if s.flags & 4 else "-") + ("W" if s.flags & 2 else "-") + ("X" if s.flags & 1 else "-")}
            for s in elf.segments]
    secs = [{"name": s.name, "addr": f"0x{s.addr:08x}", "size": s.size} for s in elf.sections]

    progress("Desmontando segmentos executáveis", 20)
    cats: Counter = Counter()
    mnems: Counter = Counter()
    ps2: Counter = Counter()
    unknown = 0
    total = 0
    hw: Dict[tuple, dict] = {}
    syscalls: List[dict] = []
    call_targets = set()
    window: List[Instr] = []
    exec_ranges = [(s.vaddr, s.vaddr + s.filesz) for s in elf.exec_segments()]

    def in_exec(a: int) -> bool:
        return any(lo <= a < hi for lo, hi in exec_ranges)

    for ins in _scan_text(elf):
        total += 1
        cats[ins.category] += 1
        mnems[ins.mnemonic] += 1
        if not ins.known:
            unknown += 1
        if ins.ps2_specific:
            ps2[ins.mnemonic] += 1
        if ins.kind == "call" and ins.jump_target is not None and in_exec(ins.jump_target):
            call_targets.add(ins.jump_target)
        if ins.mnemonic == "lui":
            hi = (ins.word & 0xFFFF)
            if hi in HW_REGIONS:
                hw.setdefault((hi,), {"region": f"0x{hi:04x}xxxx", "description": HW_REGIONS[hi],
                                      "first_at": f"0x{ins.addr:08x}", "count": 0})["count"] += 1
        if ins.kind == "syscall":
            num = None
            for prev in reversed(window[-6:]):
                # li $v1, N  => addiu/ori $v1, $zero, N   (rt == 3)
                rt = (prev.word >> 16) & 31
                rs = (prev.word >> 21) & 31
                if prev.mnemonic in ("addiu", "ori") and rt == 3 and rs == 0:
                    imm = prev.word & 0xFFFF
                    num = imm - 0x10000 if prev.mnemonic == "addiu" and imm & 0x8000 else imm
                    break
            syscalls.append({"addr": f"0x{ins.addr:08x}", "number": num})
        window.append(ins)
        if len(window) > 16:
            window.pop(0)

    progress("Descobrindo funções", 45)
    entries = {elf.entry} if in_exec(elf.entry) else set()
    entries |= call_targets
    names: Dict[int, str] = {}
    for sym in elf.symbols:
        if sym.type == STT_FUNC and in_exec(sym.value):
            entries.add(sym.value)
            names[sym.value] = sym.name
    names.setdefault(elf.entry, names.get(elf.entry, "_start/entry"))

    progress("Traduzindo funções (subconjunto suportado)", 60)
    funcs: List[FuncResult] = []
    ordered = sorted(entries)
    for i, e in enumerate(ordered):
        funcs.append(translate_function(elf.read32, e, names.get(e, "")))
        if i % 50 == 0 and ordered:
            progress("Traduzindo funções (subconjunto suportado)", 60 + int(35 * i / len(ordered)))

    unsup: Counter = Counter()
    for f in funcs:
        for u in f.unsupported:
            unsup[u["mnemonic"] + " — " + u["reason"]] += 1
    n_insn = sum(f.n_insns for f in funcs)
    n_bad = sum(f.n_unsupported for f in funcs)
    pct = round(100.0 * (n_insn - n_bad) / n_insn, 1) if n_insn else 0.0
    level, label, notes = port_status(funcs, list(hw.values()))
    progress("Concluído", 100)
    return ElfAnalysis(
        entry=elf.entry, kind=elf.kind, looks_like_ee=elf.looks_like_ee,
        sha256=hashlib.sha256(data).hexdigest(), size=len(data), segments=segs, sections=secs,
        n_symbols=len(elf.symbols), n_instructions=total, categories=dict(cats),
        mnemonics_top=dict(mnems.most_common(15)), ps2_specific=dict(ps2), unknown_words=unknown,
        functions=funcs, hardware_refs=list(hw.values()), syscalls=syscalls,
        unsupported_summary=dict(unsup.most_common()), translated_pct=pct,
        port_level=level, port_label=label, port_notes=notes)


@dataclass
class IsoReport:
    path: str
    system_id: str
    volume_id: str
    sector_layout: str
    total_size: int
    n_files: int
    n_dirs: int
    platform: str
    boot_key: Optional[str]
    boot_path: Optional[str]
    system_cnf: Dict[str, str]
    files: List[dict]
    executables: List[dict]
    main_executable: Optional[dict]
    warnings: List[str]
    elf: Optional[ElfAnalysis] = None

    def to_dict(self) -> dict:
        d = {k: v for k, v in self.__dict__.items() if k != "elf"}
        d["elf"] = self.elf.to_dict() if self.elf else None
        return d


MAX_ELF_BYTES = 64 * 1024 * 1024


def analyze_iso(path: str, progress: ProgressCb = _noop, analyze_main: bool = True) -> IsoReport:
    warnings: List[str] = []
    progress("Abrindo imagem ISO9660", 3)
    with IsoImage(path) as iso:
        entries = iso.walk()
        progress("Listando arquivos", 15)
        files, execs = [], []
        for e in entries:
            if e.is_dir:
                continue
            head = iso.read_file(e, 32)
            fmt = identify(head, e.name)
            rec = {"path": e.path, "lba": e.lba, "size": e.size, "format": fmt}
            files.append(rec)
            if fmt and (fmt.startswith("ELF") or fmt.startswith("IRX") or fmt.startswith("PS-X")):
                execs.append(rec)
        cnf_entry = iso.find("/SYSTEM.CNF", entries)
        cnf = None
        main = None
        if cnf_entry is None:
            warnings.append("SYSTEM.CNF não encontrado: não é possível determinar o executável principal.")
        else:
            cnf = parse_system_cnf(iso.read_file(cnf_entry, 4096).decode("ascii", "replace"))
            bp = cnf.boot_path
            if bp:
                me = iso.find(bp, entries)
                if me is None:
                    warnings.append(f"Executável de boot '{bp}' citado no SYSTEM.CNF não existe na imagem.")
                else:
                    main = next((f for f in files if f["path"] == me.path), None)
        if cnf is not None and cnf.boot_key == "BOOT":
            warnings.append("Disco de PlayStation 1 (BOOT=): fora do escopo deste analisador.")
        rep = IsoReport(
            path=path, system_id=iso.system_id, volume_id=iso.volume_id,
            sector_layout=f"{iso.sector_size} bytes/setor (offset de dados {iso.data_offset})",
            total_size=iso.total_size, n_files=len(files),
            n_dirs=sum(1 for e in entries if e.is_dir),
            platform=cnf.platform if cnf else "desconhecida",
            boot_key=cnf.boot_key if cnf else None, boot_path=cnf.boot_path if cnf else None,
            system_cnf=dict(cnf.values) if cnf else {}, files=files, executables=execs,
            main_executable=main, warnings=warnings)
        if analyze_main and main and (main.get("format") or "").startswith("ELF"):
            if main["size"] > MAX_ELF_BYTES:
                warnings.append("Executável principal grande demais para análise automática.")
            else:
                me = iso.find(main["path"], entries)
                data = iso.read_file(me)

                def sub(stage: str, pct: int) -> None:
                    progress(stage, 25 + int(pct * 0.75))

                try:
                    rep.elf = analyze_elf(data, sub)
                except ElfError as ex:
                    warnings.append(f"Falha ao analisar o ELF principal: {ex}")
        elif analyze_main and main:
            warnings.append("Executável principal não é um ELF reconhecido (pode estar empacotado/criptografado).")
    progress("Concluído", 100)
    return rep
