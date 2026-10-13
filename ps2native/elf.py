"""Parser de ELF32 little-endian focado em executáveis do PS2 (EE) e módulos IRX."""
from __future__ import annotations

import struct
from dataclasses import dataclass, field
from typing import List, Optional

ET_EXEC = 2
ET_IRX = 0xFF80  # módulos IOP (IRX) usam um e_type próprio
EM_MIPS = 8
PT_LOAD = 1
PF_X, PF_W, PF_R = 1, 2, 4
STT_FUNC = 2


class ElfError(Exception):
    pass


@dataclass
class Segment:
    type: int
    offset: int
    vaddr: int
    filesz: int
    memsz: int
    flags: int

    @property
    def executable(self) -> bool:
        return bool(self.flags & PF_X)


@dataclass
class Section:
    name: str
    type: int
    addr: int
    offset: int
    size: int
    flags: int


@dataclass
class Symbol:
    name: str
    value: int
    size: int
    type: int


@dataclass
class Elf:
    data: bytes
    e_type: int
    machine: int
    entry: int
    flags: int
    segments: List[Segment] = field(default_factory=list)
    sections: List[Section] = field(default_factory=list)
    symbols: List[Symbol] = field(default_factory=list)

    @property
    def kind(self) -> str:
        if self.e_type == ET_IRX:
            return "IRX (módulo do IOP)"
        if self.e_type == ET_EXEC and self.machine == EM_MIPS:
            return "ELF executável MIPS (provável EE do PS2)"
        return f"ELF e_type=0x{self.e_type:x} machine={self.machine}"

    @property
    def looks_like_ee(self) -> bool:
        # Heurística: ET_EXEC + MIPS + flags típicos do R5900 (0x20924001).
        # Não é prova; apenas um indício.
        return self.e_type == ET_EXEC and self.machine == EM_MIPS and (self.flags & 0x00900000) != 0

    def exec_segments(self) -> List[Segment]:
        return [s for s in self.segments if s.type == PT_LOAD and s.executable and s.filesz]

    def read32(self, vaddr: int) -> Optional[int]:
        for s in self.segments:
            if s.type == PT_LOAD and s.vaddr <= vaddr and vaddr + 4 <= s.vaddr + s.filesz:
                o = s.offset + (vaddr - s.vaddr)
                return struct.unpack_from("<I", self.data, o)[0]
        return None


def parse_elf(data: bytes) -> Elf:
    if len(data) < 52 or data[:4] != b"\x7fELF":
        raise ElfError("Não é um ELF (magic ausente)")
    if data[4] != 1 or data[5] != 1:
        raise ElfError("Apenas ELF32 little-endian é suportado (PS2 EE/IOP)")
    (e_type, machine, _ver, entry, phoff, shoff, flags, _eh, phentsize, phnum,
     shentsize, shnum, shstrndx) = struct.unpack_from("<HHIIIIIHHHHHH", data, 16)
    elf = Elf(data, e_type, machine, entry, flags)
    if phnum and phentsize < 32:
        raise ElfError("phentsize inválido")
    for i in range(phnum):
        o = phoff + i * phentsize
        if o + 32 > len(data):
            raise ElfError("Program header fora do arquivo")
        t, off, va, _pa, fsz, msz, fl, _al = struct.unpack_from("<8I", data, o)
        if t == PT_LOAD and off + fsz > len(data):
            raise ElfError("Segmento PT_LOAD excede o tamanho do arquivo (arquivo truncado?)")
        elf.segments.append(Segment(t, off, va, fsz, msz, fl))
    raw_secs = []
    if shoff and shnum and shentsize >= 40:
        for i in range(shnum):
            o = shoff + i * shentsize
            if o + 40 > len(data):
                break
            raw_secs.append(struct.unpack_from("<10I", data, o))
    names = b""
    if raw_secs and shstrndx < len(raw_secs):
        s = raw_secs[shstrndx]
        names = data[s[4]:s[4] + s[5]]

    def cstr(blob: bytes, off: int) -> str:
        end = blob.find(b"\0", off)
        return blob[off:end if end >= 0 else None].decode("ascii", "replace")

    for (nm, ty, fl, addr, off, size, link, _info, _al, _es) in raw_secs:
        elf.sections.append(Section(cstr(names, nm) if names else "", ty, addr, off, size, fl))
    for idx, (nm, ty, fl, addr, off, size, link, _info, _al, es) in enumerate(raw_secs):
        if ty == 2 and es == 16 and link < len(raw_secs):  # SHT_SYMTAB
            strsec = raw_secs[link]
            strtab = data[strsec[4]:strsec[4] + strsec[5]]
            for j in range(size // 16):
                o = off + j * 16
                if o + 16 > len(data):
                    break
                st_name, st_value, st_size, st_info, _oth, _shndx = struct.unpack_from("<IIIBBH", data, o)
                if st_name:
                    elf.symbols.append(Symbol(cstr(strtab, st_name), st_value, st_size, st_info & 0xF))
    return elf
