"""IR mínimo (árvore de expressões de 64 bits) para o subconjunto traduzível do R5900.

Cada instrução suportada é "levantada" (lift) para uma lista de statements. O MESMO IR
é (a) interpretado em Python (para testes de semântica) e (b) emitido como C.
Tudo que não tem semântica equivalente implementada levanta `Unsupported` com o motivo —
nada é ignorado silenciosamente.

Modelo de estado: 32 GPRs de 64 bits (a metade alta dos 128 bits NÃO é modelada, logo
lq/sq e MMI são não suportados), HI/LO de 64 bits, memória plana little-endian com
máscara de endereço (sem TLB, sem cache, sem exceções de alinhamento).
"""
from __future__ import annotations

from typing import List, Tuple

from .mips import Instr, sext

M32 = 0xFFFFFFFF
M64 = (1 << 64) - 1


class Unsupported(Exception):
    pass


def s64(v: int) -> int:
    return sext(v, 64)


def sx32(v: int) -> int:
    return sext(v, 32) & M64


Expr = tuple
Stmt = tuple


def R(n: int) -> Expr:
    return ("const", 0) if n == 0 else ("reg", n)


def C(v: int) -> Expr:
    return ("const", v & M64)


_UNSUPPORTED_REASONS = {
    "add": "add com trap de overflow (exceção não modelada)",
    "addi": "addi com trap de overflow (exceção não modelada)",
    "sub": "sub com trap de overflow (exceção não modelada)",
    "div": "div: semântica de divisão por zero/overflow do R5900 não verificada",
    "divu": "divu: semântica de divisão por zero do R5900 não verificada",
    "lq": "acesso de 128 bits: metade alta dos GPRs não é modelada",
    "sq": "acesso de 128 bits: metade alta dos GPRs não é modelada",
    "lwl": "acesso desalinhado (lwl/lwr/swl/swr) não implementado",
    "lwr": "acesso desalinhado (lwl/lwr/swl/swr) não implementado",
    "swl": "acesso desalinhado (lwl/lwr/swl/swr) não implementado",
    "swr": "acesso desalinhado (lwl/lwr/swl/swr) não implementado",
    "syscall": "syscall exige runtime do kernel/BIOS do PS2 (não implementado)",
}


def reason_for(ins: Instr) -> str:
    mn = ins.mnemonic
    if mn in _UNSUPPORTED_REASONS:
        return _UNSUPPORTED_REASONS[mn]
    if ins.category == "mmi":
        return "instrução MMI (SIMD 128-bit do PS2): requer GPRs de 128 bits"
    if ins.category == "vu0":
        return "instrução VU0/COP2: requer modelo da unidade vetorial"
    if ins.category == "fpu":
        return "FPU do EE (não é IEEE-754 completo): semântica específica não implementada"
    if ins.category == "cop0":
        return "COP0 (sistema/TLB/exceções) não modelado"
    if not ins.known:
        return "opcode desconhecido/dado dentro de segmento executável"
    if ins.mnemonic.startswith("d") or ins.mnemonic in ("ld", "sd", "ldl", "ldr", "sdl", "sdr"):
        return "operação de 64 bits ainda não implementada no tradutor"
    if ins.likely:
        return "branch-likely ainda não implementado"
    return f"instrução '{mn}' ainda não implementada no tradutor"


def lift(ins: Instr) -> List[Stmt]:
    """Levanta uma instrução NÃO-controle-de-fluxo. Branches/jumps são tratados em translator.py."""
    w = ins.word
    rs, rt, rd = (w >> 21) & 31, (w >> 16) & 31, (w >> 11) & 31
    sa = (w >> 6) & 31
    imm = w & 0xFFFF
    simm = imm - 0x10000 if imm & 0x8000 else imm
    mn = ins.mnemonic
    if mn == "nop":
        return []

    def setr(n: int, e: Expr) -> List[Stmt]:
        return [] if n == 0 else [("set", n, e)]

    alu3 = {"addu": lambda a, b: ("sext32", ("add", a, b)),
            "subu": lambda a, b: ("sext32", ("sub", a, b)),
            "and": lambda a, b: ("and", a, b), "or": lambda a, b: ("or", a, b),
            "xor": lambda a, b: ("xor", a, b), "nor": lambda a, b: ("nor", a, b),
            "slt": lambda a, b: ("slt", a, b), "sltu": lambda a, b: ("sltu", a, b)}
    if mn in alu3:
        return setr(rd, alu3[mn](R(rs), R(rt)))
    if mn in ("sll", "srl", "sra"):
        op = {"sll": "shl32", "srl": "shr32", "sra": "sar32"}[mn]
        return setr(rd, (op, R(rt), C(sa)))
    if mn in ("sllv", "srlv", "srav"):
        op = {"sllv": "shl32", "srlv": "shr32", "srav": "sar32"}[mn]
        return setr(rd, (op, R(rt), ("and", R(rs), C(31))))
    if mn == "addiu":
        return setr(rt, ("sext32", ("add", R(rs), C(simm))))
    if mn == "slti":
        return setr(rt, ("slt", R(rs), C(simm)))
    if mn == "sltiu":
        return setr(rt, ("sltu", R(rs), C(simm)))
    if mn in ("andi", "ori", "xori"):
        return setr(rt, ({"andi": "and", "ori": "or", "xori": "xor"}[mn], R(rs), C(imm)))
    if mn == "lui":
        return setr(rt, ("sext32", C(imm << 16)))
    if mn == "movz":
        return setr(rd, ("sel", ("eq0", R(rt)), R(rs), R(rd)))
    if mn == "movn":
        return setr(rd, ("sel", ("ne0", R(rt)), R(rs), R(rd)))
    if mn in ("mult", "multu"):
        sfx = "s" if mn == "mult" else "u"
        st: List[Stmt] = [("setlo", ("mullo_" + sfx, R(rs), R(rt))),
                          ("sethi", ("mulhi_" + sfx, R(rs), R(rt)))]
        return st + setr(rd, ("lo",))
    if mn == "mfhi":
        return setr(rd, ("hi",))
    if mn == "mflo":
        return setr(rd, ("lo",))
    if mn == "mthi":
        return [("sethi", R(rs))]
    if mn == "mtlo":
        return [("setlo", R(rs))]
    loads = {"lb": (1, True), "lbu": (1, False), "lh": (2, True), "lhu": (2, False),
             "lw": (4, True), "lwu": (4, False), "ld": (8, False)}
    if mn in loads:
        size, sgn = loads[mn]
        addr = ("zext32", ("add", R(rs), C(simm)))
        return setr(rt, ("load", size, sgn, addr))
    stores = {"sb": 1, "sh": 2, "sw": 4, "sd": 8}
    if mn in stores:
        addr = ("zext32", ("add", R(rs), C(simm)))
        return [("store", stores[mn], addr, R(rt))]
    raise Unsupported(reason_for(ins))


def cond_expr(ins: Instr) -> Expr:
    w = ins.word
    rs, rt = (w >> 21) & 31, (w >> 16) & 31
    mn = ins.mnemonic
    if ins.likely:
        raise Unsupported("branch-likely ainda não implementado")
    table = {"beq": ("eq", R(rs), R(rt)), "bne": ("ne", R(rs), R(rt)),
             "blez": ("lez", R(rs), C(0)), "bgtz": ("gtz", R(rs), C(0)),
             "bltz": ("ltz", R(rs), C(0)), "bgez": ("gez", R(rs), C(0))}
    if mn in table:
        return table[mn]
    raise Unsupported(f"branch '{mn}' não suportado (COP/link/likely)")


# ----------------------------------------------------------------------------
# Interpretador Python do IR (referência de semântica para testes)
# ----------------------------------------------------------------------------
class State:
    def __init__(self, mem_size: int = 1 << 20):
        assert mem_size & (mem_size - 1) == 0
        self.r = [0] * 32
        self.hi = 0
        self.lo = 0
        self.mem = bytearray(mem_size)
        self.mask = mem_size - 1

    def load(self, addr: int, size: int, signed: bool) -> int:
        a = addr & self.mask
        v = int.from_bytes(self.mem[a:a + size], "little")
        if signed:
            v = sext(v, size * 8)
        return v & M64

    def store(self, addr: int, size: int, val: int) -> None:
        a = addr & self.mask
        self.mem[a:a + size] = (val & ((1 << (size * 8)) - 1)).to_bytes(size, "little")


def eval_expr(e: Expr, st: State) -> int:
    k = e[0]
    if k == "const":
        return e[1] & M64
    if k == "reg":
        return st.r[e[1]] & M64
    if k == "hi":
        return st.hi
    if k == "lo":
        return st.lo
    if k == "load":
        return st.load(eval_expr(e[3], st), e[1], e[2])
    if k == "sel":
        return eval_expr(e[2], st) if eval_expr(e[1], st) else eval_expr(e[3], st)
    a = eval_expr(e[1], st)
    if k == "sext32":
        return sx32(a)
    if k == "zext32":
        return a & M32
    if k == "eq0":
        return int(a == 0)
    if k == "ne0":
        return int(a != 0)
    if k == "lez":
        return int(s64(a) <= 0)
    if k == "gtz":
        return int(s64(a) > 0)
    if k == "ltz":
        return int(s64(a) < 0)
    if k == "gez":
        return int(s64(a) >= 0)
    b = eval_expr(e[2], st)
    if k == "add":
        return (a + b) & M64
    if k == "sub":
        return (a - b) & M64
    if k == "and":
        return a & b
    if k == "or":
        return a | b
    if k == "xor":
        return a ^ b
    if k == "nor":
        return ~(a | b) & M64
    if k == "slt":
        return int(s64(a) < s64(b))
    if k == "sltu":
        return int(a < b)
    if k == "eq":
        return int(a == b)
    if k == "ne":
        return int(a != b)
    if k == "shl32":
        return sx32((a << (b & 31)) & M32)
    if k == "shr32":
        return sx32((a & M32) >> (b & 31))
    if k == "sar32":
        return sx32(sext(a & M32, 32) >> (b & 31))
    if k in ("mullo_s", "mulhi_s"):
        p = (sext(a & M32, 32) * sext(b & M32, 32)) & M64
        return sx32(p if k == "mullo_s" else p >> 32)
    if k in ("mullo_u", "mulhi_u"):
        p = (a & M32) * (b & M32)
        return sx32(p if k == "mullo_u" else p >> 32)
    raise ValueError(f"expressão desconhecida: {k}")


def exec_stmt(s: Stmt, st: State) -> None:
    k = s[0]
    if k == "set":
        st.r[s[1]] = eval_expr(s[2], st)
    elif k == "sethi":
        st.hi = eval_expr(s[1], st)
    elif k == "setlo":
        st.lo = eval_expr(s[1], st)
    elif k == "store":
        st.store(eval_expr(s[2], st), s[1], eval_expr(s[3], st))
    else:
        raise ValueError(k)
    st.r[0] = 0


# ----------------------------------------------------------------------------
# Emissão de C
# ----------------------------------------------------------------------------
def c_expr(e: Expr) -> str:
    k = e[0]
    if k == "const":
        return f"0x{e[1] & M64:x}ULL"
    if k == "reg":
        return f"c->r[{e[1]}]"
    if k == "hi":
        return "c->hi"
    if k == "lo":
        return "c->lo"
    if k == "load":
        return f"ps2_load(c, (uint32_t)({c_expr(e[3])}), {e[1]}, {int(e[2])})"
    if k == "sel":
        return f"(({c_expr(e[1])}) ? ({c_expr(e[2])}) : ({c_expr(e[3])}))"
    a = c_expr(e[1])
    if k == "sext32":
        return f"PS2_SEXT32({a})"
    if k == "zext32":
        return f"(({a}) & 0xFFFFFFFFULL)"
    if k == "eq0":
        return f"((uint64_t)(({a}) == 0))"
    if k == "ne0":
        return f"((uint64_t)(({a}) != 0))"
    if k == "lez":
        return f"((uint64_t)((int64_t)({a}) <= 0))"
    if k == "gtz":
        return f"((uint64_t)((int64_t)({a}) > 0))"
    if k == "ltz":
        return f"((uint64_t)((int64_t)({a}) < 0))"
    if k == "gez":
        return f"((uint64_t)((int64_t)({a}) >= 0))"
    b = c_expr(e[2])
    simple = {"add": "+", "sub": "-", "and": "&", "or": "|", "xor": "^"}
    if k in simple:
        return f"(({a}) {simple[k]} ({b}))"
    if k == "nor":
        return f"(~(({a}) | ({b})))"
    if k == "slt":
        return f"((uint64_t)((int64_t)({a}) < (int64_t)({b})))"
    if k == "sltu":
        return f"((uint64_t)(({a}) < ({b})))"
    if k == "eq":
        return f"((uint64_t)(({a}) == ({b})))"
    if k == "ne":
        return f"((uint64_t)(({a}) != ({b})))"
    if k == "shl32":
        return f"PS2_SEXT32((({a}) << (({b}) & 31)) & 0xFFFFFFFFULL)"
    if k == "shr32":
        return f"PS2_SEXT32((({a}) & 0xFFFFFFFFULL) >> (({b}) & 31))"
    if k == "sar32":
        return f"PS2_SEXT32((uint64_t)(int64_t)(((int32_t)(uint32_t)({a})) >> (({b}) & 31)))"
    if k in ("mullo_s", "mulhi_s"):
        p = f"((int64_t)(int32_t)(uint32_t)({a}) * (int64_t)(int32_t)(uint32_t)({b}))"
        return f"PS2_SEXT32((uint64_t){p})" if k == "mullo_s" else f"PS2_SEXT32((uint64_t)({p} >> 32))"
    if k in ("mullo_u", "mulhi_u"):
        p = f"((uint64_t)(uint32_t)({a}) * (uint64_t)(uint32_t)({b}))"
        return f"PS2_SEXT32({p})" if k == "mullo_u" else f"PS2_SEXT32({p} >> 32)"
    raise ValueError(k)


def c_stmt(s: Stmt) -> str:
    k = s[0]
    if k == "set":
        return f"c->r[{s[1]}] = {c_expr(s[2])};"
    if k == "sethi":
        return f"c->hi = {c_expr(s[1])};"
    if k == "setlo":
        return f"c->lo = {c_expr(s[1])};"
    if k == "store":
        return f"ps2_store(c, (uint32_t)({c_expr(s[2])}), {s[1]}, {c_expr(s[3])});"
    raise ValueError(k)
