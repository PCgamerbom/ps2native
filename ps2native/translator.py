"""Tradutor estático experimental: funções R5900 -> C (subconjunto com semântica verificada).

Princípios:
  * instrução sem semântica implementada NUNCA é ignorada: gera `ps2_unsupported()`
    (aborta em tempo de execução) e fica registrada no relatório;
  * status por função: translated | partial | unsupported;
  * premissas (convenção de chamada padrão, sem exceções, etc.) são listadas por função.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Callable, Dict, List, Optional

from . import ir
from .mips import Instr, decode

MAX_FUNC_INSNS = 4096

ASSUMPTIONS = [
    "jr $ra é tratado como retorno da função C; o valor de $ra não é verificado",
    "jal vira chamada C direta ps2_func_<endereço>(); callee precisa existir/ser traduzido",
    "sem exceções, sem TLB, sem cache, sem verificação de alinhamento",
    "memória plana little-endian com máscara de endereço (PS2_MEM_MASK)",
    "limites da função detectados por heurística (jr $ra + maior alvo de branch)",
]


@dataclass
class FuncResult:
    entry: int
    end: int
    n_insns: int
    status: str
    unsupported: List[dict] = field(default_factory=list)
    calls: List[int] = field(default_factory=list)
    c_source: Optional[str] = None
    name: str = ""

    @property
    def n_unsupported(self) -> int:
        return len({u["addr"] for u in self.unsupported})

    def to_dict(self) -> dict:
        return {"entry": f"0x{self.entry:08x}", "end": f"0x{self.end:08x}",
                "n_insns": self.n_insns, "status": self.status, "name": self.name,
                "unsupported": self.unsupported, "calls": [f"0x{c:08x}" for c in self.calls]}


def fname(addr: int) -> str:
    return f"ps2_func_{addr:08X}"


def find_extent(read32: Callable[[int], Optional[int]], entry: int,
                limit: int = MAX_FUNC_INSNS) -> List[Instr]:
    out: List[Instr] = []
    a, max_t = entry, entry
    while len(out) < limit:
        w = read32(a)
        if w is None:
            break
        ins = decode(w, a)
        out.append(ins)
        t = ins.branch_target if ins.kind == "branch" else ins.jump_target if ins.kind == "jump" else None
        if t is not None and a < t < a + 0x4000:
            max_t = max(max_t, t)
        if ins.kind == "return":
            sw = read32(a + 4)
            if sw is not None:
                out.append(decode(sw, a + 4))
            a += 8
            if a > max_t:
                break
            continue
        a += 4
    return out


def translate_function(read32: Callable[[int], Optional[int]], entry: int,
                       name: str = "") -> FuncResult:
    insns = find_extent(read32, entry)
    by_addr: Dict[int, Instr] = {i.addr: i for i in insns}
    end = insns[-1].addr + 4 if insns else entry
    unsup: List[dict] = []
    seen_unsup = set()
    calls: List[int] = []
    labels = set()
    chunks: Dict[int, List[str]] = {}

    def note(ins: Instr, reason: str) -> None:
        if ins.addr not in seen_unsup:
            seen_unsup.add(ins.addr)
            unsup.append({"addr": f"0x{ins.addr:08x}", "mnemonic": ins.mnemonic,
                          "text": ins.text, "reason": reason})

    def slot_stmts(branch: Instr) -> Optional[List[str]]:
        slot = by_addr.get(branch.addr + 4)
        if slot is None:
            note(branch, "delay slot fora da função")
            return None
        if slot.kind or slot.category in ("branch", "jump"):
            note(branch, "delay slot contém instrução de controle de fluxo")
            return None
        try:
            return [ir.c_stmt(s) for s in ir.lift(slot)]
        except ir.Unsupported as e:
            note(slot, str(e))
            return None

    def bail(ins: Instr, reason: str) -> List[str]:
        note(ins, reason)
        return [f"    ps2_unsupported(c, 0x{ins.addr:08X}u); /* {ins.text} */"]

    for ins in insns:
        a = ins.addr
        if ins.kind == "branch":
            try:
                cond = ir.c_expr(ir.cond_expr(ins))
            except ir.Unsupported as e:
                chunks[a] = bail(ins, str(e))
                continue
            tgt = ins.branch_target
            if tgt not in by_addr:
                chunks[a] = bail(ins, "branch para fora da função detectada")
                continue
            if a + 8 not in by_addr:
                chunks[a] = bail(ins, "fluxo de saída do branch cai fora da função detectada")
                continue
            st = slot_stmts(ins)
            if st is None:
                chunks[a] = bail(ins, "branch com delay slot não traduzível")
                continue
            labels.update([tgt, a + 8])
            chunks[a] = ([f"    {{ uint64_t cond_ = {cond};"] + [f"      {s}" for s in st] +
                         [f"      if (cond_) goto L_{tgt:08X}; goto L_{a + 8:08X}; }}"])
        elif ins.kind == "jump":
            tgt = ins.jump_target
            if tgt not in by_addr:
                chunks[a] = bail(ins, "j para fora da função (tail call/overlay) não suportado")
                continue
            st = slot_stmts(ins)
            if st is None:
                chunks[a] = bail(ins, "j com delay slot não traduzível")
                continue
            labels.add(tgt)
            chunks[a] = [f"    {s}" for s in st] + [f"    goto L_{tgt:08X};"]
        elif ins.kind == "call":
            if ins.mnemonic != "jal":
                chunks[a] = bail(ins, "branch-and-link (bltzal/bgezal) não suportado")
                continue
            if a + 8 not in by_addr:
                chunks[a] = bail(ins, "retorno do jal cai fora da função detectada")
                continue
            st = slot_stmts(ins)
            if st is None:
                chunks[a] = bail(ins, "jal com delay slot não traduzível")
                continue
            tgt = ins.jump_target
            calls.append(tgt)
            labels.add(a + 8)
            chunks[a] = ([f"    c->r[31] = 0x{a + 8:x}ULL;"] + [f"    {s}" for s in st] +
                         [f"    {fname(tgt)}(c); goto L_{a + 8:08X};"])
        elif ins.kind == "return":
            st = slot_stmts(ins)
            if st is None:
                chunks[a] = bail(ins, "jr $ra com delay slot não traduzível")
                continue
            chunks[a] = [f"    {s}" for s in st] + ["    return;"]
        elif ins.kind in ("indirect_jump", "indirect_call"):
            chunks[a] = bail(ins, "salto/chamada indireta: alvo só conhecido em tempo de execução "
                                  "(tabela de saltos ou ponteiro de função)")
        else:
            try:
                chunks[a] = [f"    {ir.c_stmt(s)}" for s in ir.lift(ins)]
            except ir.Unsupported as e:
                chunks[a] = bail(ins, str(e))

    lines = [f"void {fname(entry)}(PS2Ctx *c) {{"]
    for ins in insns:
        if ins.addr in labels:
            lines.append(f"  L_{ins.addr:08X}: ;")
        lines.append(f"    /* {ins.addr:08x}: {ins.text} */")
        lines += chunks.get(ins.addr, [])
    lines.append("}")
    n_bad = len(seen_unsup)
    if not insns:
        status = "unsupported"
    elif n_bad == 0:
        status = "translated"
    elif n_bad >= len(insns):
        status = "unsupported"
    else:
        status = "partial"
    return FuncResult(entry, end, len(insns), status, unsup, sorted(set(calls)),
                      "\n".join(lines), name or fname(entry))


RUNTIME_HEADER = r"""/* ps2rt.h — runtime MÍNIMO do PS2Native (protótipo).
 * Implementa apenas contexto de CPU + memória plana. NÃO existe GS, VU, DMA, IOP,
 * SPU2, kernel/BIOS: código que dependa deles não funciona. */
#ifndef PS2RT_H
#define PS2RT_H
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#ifndef PS2_MEM_MASK
#define PS2_MEM_MASK 0x1FFFFFFu /* 32 MB de RAM do EE */
#endif
#define PS2_SEXT32(x) ((uint64_t)(int64_t)(int32_t)(uint32_t)(x))
typedef struct { uint64_t r[32]; uint64_t hi, lo; uint8_t *mem; } PS2Ctx;
static inline uint64_t ps2_load(PS2Ctx *c, uint32_t a, int size, int is_signed) {
    uint64_t v = 0;
    for (int i = 0; i < size; i++) v |= (uint64_t)c->mem[(a + i) & PS2_MEM_MASK] << (8 * i);
    if (is_signed && size < 8) { int sh = 64 - 8 * size; v = (uint64_t)(((int64_t)(v << sh)) >> sh); }
    return v;
}
static inline void ps2_store(PS2Ctx *c, uint32_t a, int size, uint64_t v) {
    for (int i = 0; i < size; i++) c->mem[(a + i) & PS2_MEM_MASK] = (uint8_t)(v >> (8 * i));
}
static inline void ps2_unsupported(PS2Ctx *c, uint32_t addr) {
    (void)c;
    fprintf(stderr, "[PS2Native] instrução NÃO suportada executada em 0x%08X\n", addr);
    abort();
}
#endif
"""


def generate_c_unit(results: List[FuncResult], only_translated: bool = False) -> str:
    funcs = [r for r in results if r.c_source and (r.status == "translated" or not only_translated)]
    defined = {r.entry for r in funcs}
    externs = sorted({c for r in funcs for c in r.calls} - defined)
    out = ['#include "ps2rt.h"', ""]
    out += [f"extern void {fname(a)}(PS2Ctx *c); /* NÃO traduzida/definida */" for a in externs]
    out += [f"void {fname(r.entry)}(PS2Ctx *c);" for r in funcs]
    out.append("")
    for r in funcs:
        out.append(f"/* status: {r.status}; instruções: {r.n_insns}; "
                   f"não suportadas: {r.n_unsupported} */")
        out.append(r.c_source)
        out.append("")
    return "\n".join(out)
