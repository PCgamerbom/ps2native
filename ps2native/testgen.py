"""Geradores de dados de teste PRÓPRIOS (sem material comercial): mini-assembler MIPS,
construtor de ELF32 e construtor de ISO9660. Também usados para gerar uma ISO de demonstração."""
from __future__ import annotations

import struct
from typing import Dict, List, Tuple

# ---- mini-assembler -------------------------------------------------------------
Z, AT, V0, V1, A0, A1, A2, A3 = range(8)
T0, T1, T2, T3 = 8, 9, 10, 11
SP, RA = 29, 31


def r_type(fn: int, rs=0, rt=0, rd=0, sa=0, op=0) -> int:
    return (op << 26) | (rs << 21) | (rt << 16) | (rd << 11) | (sa << 6) | fn


def i_type(op: int, rs: int, rt: int, imm: int) -> int:
    return (op << 26) | (rs << 21) | (rt << 16) | (imm & 0xFFFF)


def addu(rd, rs, rt): return r_type(33, rs, rt, rd)
def subu(rd, rs, rt): return r_type(35, rs, rt, rd)
def and_(rd, rs, rt): return r_type(36, rs, rt, rd)
def or_(rd, rs, rt): return r_type(37, rs, rt, rd)
def xor_(rd, rs, rt): return r_type(38, rs, rt, rd)
def nor(rd, rs, rt): return r_type(39, rs, rt, rd)
def slt(rd, rs, rt): return r_type(42, rs, rt, rd)
def sltu(rd, rs, rt): return r_type(43, rs, rt, rd)
def sll(rd, rt, sa): return r_type(0, 0, rt, rd, sa)
def srl(rd, rt, sa): return r_type(2, 0, rt, rd, sa)
def sra(rd, rt, sa): return r_type(3, 0, rt, rd, sa)
def sllv(rd, rt, rs): return r_type(4, rs, rt, rd)
def srav(rd, rt, rs): return r_type(7, rs, rt, rd)
def mult(rs, rt): return r_type(24, rs, rt)
def multu(rs, rt): return r_type(25, rs, rt)
def div(rs, rt): return r_type(26, rs, rt)
def mfhi(rd): return r_type(16, rd=rd)
def mflo(rd): return r_type(18, rd=rd)
def movz(rd, rs, rt): return r_type(10, rs, rt, rd)
def movn(rd, rs, rt): return r_type(11, rs, rt, rd)
def jr(rs): return r_type(8, rs)
def syscall(): return r_type(12)
def addiu(rt, rs, imm): return i_type(9, rs, rt, imm)
def slti(rt, rs, imm): return i_type(10, rs, rt, imm)
def sltiu(rt, rs, imm): return i_type(11, rs, rt, imm)
def andi(rt, rs, imm): return i_type(12, rs, rt, imm)
def ori(rt, rs, imm): return i_type(13, rs, rt, imm)
def xori(rt, rs, imm): return i_type(14, rs, rt, imm)
def lui(rt, imm): return i_type(15, 0, rt, imm)
def lb(rt, off, rs): return i_type(32, rs, rt, off)
def lh(rt, off, rs): return i_type(33, rs, rt, off)
def lw(rt, off, rs): return i_type(35, rs, rt, off)
def lbu(rt, off, rs): return i_type(36, rs, rt, off)
def lhu(rt, off, rs): return i_type(37, rs, rt, off)
def sb(rt, off, rs): return i_type(40, rs, rt, off)
def sh(rt, off, rs): return i_type(41, rs, rt, off)
def sw(rt, off, rs): return i_type(43, rs, rt, off)
def lq(rt, off, rs): return i_type(30, rs, rt, off)
def beq(rs, rt, off_words): return i_type(4, rs, rt, off_words)
def bne(rs, rt, off_words): return i_type(5, rs, rt, off_words)
def bgez(rs, off_words): return (1 << 26) | (rs << 21) | (1 << 16) | (off_words & 0xFFFF)
def jal(addr): return (3 << 26) | ((addr >> 2) & 0x3FFFFFF)
def j(addr): return (2 << 26) | ((addr >> 2) & 0x3FFFFFF)
def pand(rd, rs, rt): return (28 << 26) | (rs << 21) | (rt << 16) | (rd << 11) | (18 << 6) | 9
def qmtc2(rt, vf): return (18 << 26) | (5 << 21) | (rt << 16) | (vf << 11)
NOP = 0

# ---- programa de demonstração ---------------------------------------------------
BASE = 0x00100000
ADDR_MAIN = BASE
ADDR_ADD = BASE + 0x30
ADDR_LOOP = BASE + 0x3C
ADDR_PS2 = BASE + 0x60
ADDR_MEM = BASE + 0x74


def demo_program() -> Tuple[List[int], List[Tuple[str, int, int]]]:
    main = [addiu(SP, SP, -16), sw(RA, 0, SP), addiu(A0, Z, 5), jal(ADDR_ADD), addiu(A1, Z, 7),
            lui(T0, 0x1200), lw(T1, 0, T0), addiu(V1, Z, 0x3C), syscall(),
            lw(RA, 0, SP), jr(RA), addiu(SP, SP, 16)]
    add = [addu(V0, A0, A1), jr(RA), NOP]
    # soma a0 + (a0-1) + ... + 1  (0 se a0 == 0)
    loop = [addu(V0, Z, Z), beq(A0, Z, 5), NOP, addu(V0, V0, A0), addiu(A0, A0, -1),
            bne(A0, Z, -3), NOP, jr(RA), NOP]
    ps2 = [pand(V0, A0, A1), lq(T0, 0, SP), qmtc2(T0, 1), jr(RA), NOP]
    mem = [sw(A0, 0, A1), lw(V0, 0, A1), jr(RA), NOP]
    words: List[int] = []
    for addr, blk in [(ADDR_MAIN, main), (ADDR_ADD, add), (ADDR_LOOP, loop), (ADDR_PS2, ps2),
                      (ADDR_MEM, mem)]:
        while BASE + 4 * len(words) < addr:
            words.append(NOP)
        assert BASE + 4 * len(words) == addr, hex(addr)
        words += blk
    syms = [("main", ADDR_MAIN, 48), ("add", ADDR_ADD, 12), ("loop_sum", ADDR_LOOP, 36),
            ("ps2_stuff", ADDR_PS2, 20), ("mem_roundtrip", ADDR_MEM, 16)]
    return words, syms


# ---- ELF32 ---------------------------------------------------------------------
def build_elf(words: List[int], base: int = BASE, entry: int = BASE,
              symbols: List[Tuple[str, int, int]] = (), e_type: int = 2) -> bytes:
    text = b"".join(struct.pack("<I", w & 0xFFFFFFFF) for w in words)
    off_text = 0x80
    strtab = b"\0"
    symtab = b"\0" * 16
    for name, addr, size in symbols:
        symtab += struct.pack("<IIIBBH", len(strtab), addr, size, 0x12, 0, 1)
        strtab += name.encode() + b"\0"
    shstr = b"\0.text\0.symtab\0.strtab\0.shstrtab\0"
    off_symtab = off_text + len(text)
    off_strtab = off_symtab + len(symtab)
    off_shstr = off_strtab + len(strtab)
    off_sh = (off_shstr + len(shstr) + 3) & ~3
    shdrs = [struct.pack("<10I", *([0] * 10)),
             struct.pack("<10I", 1, 1, 6, base, off_text, len(text), 0, 0, 4, 0),
             struct.pack("<10I", 7, 2, 0, 0, off_symtab, len(symtab), 3, 1, 4, 16),
             struct.pack("<10I", 15, 3, 0, 0, off_strtab, len(strtab), 0, 0, 1, 0),
             struct.pack("<10I", 23, 3, 0, 0, off_shstr, len(shstr), 0, 0, 1, 0)]
    ident = b"\x7fELF" + bytes([1, 1, 1, 0]) + b"\0" * 8
    ehdr = ident + struct.pack("<HHIIIIIHHHHHH", e_type, 8, 1, entry, 52, off_sh, 0x20924001,
                               52, 32, 1, 40, len(shdrs), 4)
    phdr = struct.pack("<8I", 1, off_text, base, base, len(text), len(text), 5, 0x1000)
    out = bytearray(ehdr + phdr)
    out += b"\0" * (off_text - len(out))
    out += text + symtab + strtab + shstr
    out += b"\0" * (off_sh - len(out))
    out += b"".join(shdrs)
    return bytes(out)


# ---- ISO9660 -------------------------------------------------------------------
def _both32(v: int) -> bytes:
    return struct.pack("<I", v) + struct.pack(">I", v)


def _rec(name: bytes, lba: int, size: int, is_dir: bool) -> bytes:
    ln = 33 + len(name)
    total = ln + (ln % 2)
    b = bytearray(total)
    b[0] = total
    b[2:10] = _both32(lba)
    b[10:18] = _both32(size)
    b[18:25] = bytes([126, 1, 1, 0, 0, 0, 0])
    b[25] = 2 if is_dir else 0
    b[28:32] = struct.pack("<H", 1) + struct.pack(">H", 1)
    b[32] = len(name)
    b[33:33 + len(name)] = name
    return bytes(b)


def build_iso(files: Dict[str, bytes], raw_sectors: bool = False, volume_id: str = "PS2NATIVE_DEMO") -> bytes:
    """files: {"SYSTEM.CNF": b"..", "DATA/TEST.VAG": b".."} (um nível de subdiretório)."""
    dirs: Dict[str, List[Tuple[str, bytes]]] = {"": []}
    for path, data in files.items():
        d, _, n = path.rpartition("/")
        dirs.setdefault(d, []).append((n, data))
    dir_names = [d for d in dirs if d]
    dir_lba = {"": 18}
    for i, d in enumerate(dir_names):
        dir_lba[d] = 19 + i
    next_lba = 19 + len(dir_names)
    file_lba: Dict[str, int] = {}
    for path in files:
        file_lba[path] = next_lba
        next_lba += max(1, -(-len(files[path]) // 2048))
    sectors: Dict[int, bytes] = {}
    for d, entries in dirs.items():
        parent = dir_lba[""] if d else dir_lba[""]
        body = _rec(b"\x00", dir_lba[d], 2048, True) + _rec(b"\x01", parent, 2048, True)
        if d == "":
            for sub in dir_names:
                body += _rec(sub.encode(), dir_lba[sub], 2048, True)
        for n, data in entries:
            p = (d + "/" if d else "") + n
            body += _rec((n + ";1").encode(), file_lba[p], len(data), False)
        assert len(body) <= 2048
        sectors[dir_lba[d]] = body.ljust(2048, b"\0")
    for path, data in files.items():
        lba = file_lba[path]
        for i in range(max(1, -(-len(data) // 2048))):
            sectors[lba + i] = data[i * 2048:(i + 1) * 2048].ljust(2048, b"\0")
    pvd = bytearray(2048)
    pvd[0] = 1
    pvd[1:6] = b"CD001"
    pvd[6] = 1
    pvd[8:40] = b"PLAYSTATION".ljust(32)
    pvd[40:72] = volume_id.encode().ljust(32)
    pvd[80:88] = _both32(next_lba)
    pvd[120:124] = struct.pack("<H", 1) + struct.pack(">H", 1)
    pvd[128:132] = struct.pack("<H", 2048) + struct.pack(">H", 2048)
    pvd[156:190] = _rec(b"\x00", 18, 2048, True)
    sectors[16] = bytes(pvd)
    term = bytearray(2048)
    term[0] = 255
    term[1:6] = b"CD001"
    term[6] = 1
    sectors[17] = bytes(term)
    out = bytearray()
    for lba in range(next_lba):
        data = sectors.get(lba, b"\0" * 2048)
        if raw_sectors:
            out += b"\x00" + b"\xff" * 10 + b"\x00" + b"\x00\x02\x00\x01" + data + b"\0" * 288
        else:
            out += data
    return bytes(out)


def demo_iso(raw_sectors: bool = False) -> bytes:
    words, syms = demo_program()
    elf = build_elf(words, symbols=syms)
    cnf = b"BOOT2 = cdrom0:\\SLUS_999.99;1\r\nVER = 1.00\r\nVMODE = NTSC\r\n"
    vag = b"VAGp" + b"\0" * 60
    return build_iso({"SYSTEM.CNF": cnf, "SLUS_999.99": elf, "DATA/TEST.VAG": vag},
                     raw_sectors=raw_sectors)
