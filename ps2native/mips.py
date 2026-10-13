"""Decodificador/desmontador do MIPS R5900 (Emotion Engine do PS2).

Cobre MIPS III/IV básico, COP0, COP1 (FPU), MMI e marca instruções específicas
do PS2. Instruções VU0 em modo macro (COP2) são reconhecidas apenas de forma
genérica (sem nome/operandos individuais): isso é uma LIMITAÇÃO conhecida.
Nomes das tabelas MMI foram escritos a partir do manual do EE e devem ser
revisados contra a documentação oficial/PCSX2 antes de uso sério.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

REGS = ["zero", "at", "v0", "v1", "a0", "a1", "a2", "a3",
        "t0", "t1", "t2", "t3", "t4", "t5", "t6", "t7",
        "s0", "s1", "s2", "s3", "s4", "s5", "s6", "s7",
        "t8", "t9", "k0", "k1", "gp", "sp", "fp", "ra"]


def sext(v: int, bits: int) -> int:
    v &= (1 << bits) - 1
    return v - (1 << bits) if v & (1 << (bits - 1)) else v


@dataclass
class Instr:
    addr: int
    word: int
    mnemonic: str
    operands: str = ""
    category: str = "unknown"  # alu mem branch jump fpu mmi vu0 cop0 syscall system unknown
    ps2_specific: bool = False
    known: bool = True
    kind: str = ""  # branch jump call return indirect_jump indirect_call syscall
    likely: bool = False
    branch_target: Optional[int] = None
    jump_target: Optional[int] = None

    @property
    def has_delay_slot(self) -> bool:
        return self.kind in ("branch", "jump", "call", "return", "indirect_jump", "indirect_call")

    @property
    def text(self) -> str:
        return f"{self.mnemonic} {self.operands}".strip()


_RD_RS_RT = {10: "movz", 11: "movn", 32: "add", 33: "addu", 34: "sub", 35: "subu", 36: "and",
             37: "or", 38: "xor", 39: "nor", 42: "slt", 43: "sltu", 44: "dadd", 45: "daddu",
             46: "dsub", 47: "dsubu"}
_SH_IMM = {0: "sll", 2: "srl", 3: "sra", 56: "dsll", 58: "dsrl", 59: "dsra",
           60: "dsll32", 62: "dsrl32", 63: "dsra32"}
_SH_VAR = {4: "sllv", 6: "srlv", 7: "srav", 20: "dsllv", 22: "dsrlv", 23: "dsrav"}
_RS_RT = {24: "mult", 25: "multu", 26: "div", 27: "divu", 48: "tge", 49: "tgeu",
          50: "tlt", 51: "tltu", 52: "teq", 54: "tne"}
_IMM_SIGNED = {8: "addi", 9: "addiu", 10: "slti", 11: "sltiu", 24: "daddi", 25: "daddiu"}
_IMM_LOGIC = {12: "andi", 13: "ori", 14: "xori"}
_MEM = {32: "lb", 33: "lh", 34: "lwl", 35: "lw", 36: "lbu", 37: "lhu", 38: "lwr", 39: "lwu",
        40: "sb", 41: "sh", 42: "swl", 43: "sw", 44: "sdl", 45: "sdr", 46: "swr",
        26: "ldl", 27: "ldr", 55: "ld", 63: "sd", 30: "lq", 31: "sq"}
_BR2 = {4: "beq", 5: "bne", 20: "beql", 21: "bnel"}
_BR1 = {6: "blez", 7: "bgtz", 22: "blezl", 23: "bgtzl"}
_REGIMM = {0: "bltz", 1: "bgez", 2: "bltzl", 3: "bgezl", 16: "bltzal", 17: "bgezal",
           18: "bltzall", 19: "bgezall"}
_MMI_TOP = {0: "madd", 1: "maddu", 4: "plzcw", 16: "mfhi1", 17: "mthi1", 18: "mflo1",
            19: "mtlo1", 24: "mult1", 25: "multu1", 26: "div1", 27: "divu1", 32: "madd1",
            33: "maddu1", 52: "psllh", 54: "psrlh", 55: "psrah", 60: "psllw", 62: "psrlw",
            63: "psraw"}
_MMI0 = {0: "paddw", 1: "psubw", 2: "pcgtw", 3: "pmaxw", 4: "paddh", 5: "psubh", 6: "pcgth",
         7: "pmaxh", 8: "paddb", 9: "psubb", 10: "pcgtb", 16: "paddsw", 17: "psubsw",
         18: "pextlw", 19: "ppacw", 20: "paddsh", 21: "psubsh", 22: "pextlh", 23: "ppach",
         24: "paddsb", 25: "psubsb", 26: "pextlb", 27: "ppacb", 30: "pext5", 31: "ppac5"}
_MMI1 = {1: "pabsw", 2: "pceqw", 3: "pminw", 4: "padsbh", 5: "pabsh", 6: "pceqh", 7: "pminh",
         10: "pceqb", 16: "padduw", 17: "psubuw", 18: "pextuw", 20: "padduh", 21: "psubuh",
         22: "pextuh", 24: "paddub", 25: "psubub", 26: "pextub", 27: "qfsrv"}
_MMI2 = {0: "pmaddw", 2: "psllvw", 3: "psrlvw", 4: "pmsubw", 8: "pmfhi", 9: "pmflo",
         10: "pinth", 12: "pmultw", 13: "pdivw", 14: "pcpyld", 16: "pmaddh", 17: "phmadh",
         18: "pand", 19: "pxor", 20: "pmsubh", 21: "phmsbh", 26: "pexeh", 27: "prevh",
         28: "pmulth", 29: "pdivbw", 30: "pexew", 31: "prot3w"}
_MMI3 = {0: "pmadduw", 3: "psravw", 8: "pmthi", 9: "pmtlo", 10: "pinteh", 12: "pmultuw",
         13: "pdivuw", 14: "pcpyud", 18: "por", 19: "pnor", 26: "pexch", 27: "pcpyh",
         30: "pexcw"}
_PMFHL = {0: "lw", 1: "uw", 2: "slw", 3: "lh", 4: "sh"}
_COP1_S = {0: "add.s", 1: "sub.s", 2: "mul.s", 3: "div.s", 4: "sqrt.s", 5: "abs.s",
           6: "mov.s", 7: "neg.s", 22: "rsqrt.s", 24: "adda.s", 25: "suba.s", 26: "mula.s",
           28: "madd.s", 29: "msub.s", 30: "madda.s", 31: "msuba.s", 36: "cvt.w.s",
           40: "max.s", 41: "min.s", 48: "c.f.s", 50: "c.eq.s", 52: "c.lt.s", 54: "c.le.s"}
_BCCOND = {0: "f", 1: "t", 2: "fl", 3: "tl"}


def decode(word: int, addr: int = 0) -> Instr:
    word &= 0xFFFFFFFF
    op = (word >> 26) & 63
    rs, rt, rd = (word >> 21) & 31, (word >> 16) & 31, (word >> 11) & 31
    sa, fn = (word >> 6) & 31, word & 63
    imm = word & 0xFFFF
    simm = sext(imm, 16)

    def r(n: int) -> str:
        return "$" + REGS[n]

    def I(mn, ops="", cat="alu", **kw):
        return Instr(addr, word, mn, ops, cat, **kw)

    def unk():
        return Instr(addr, word, ".word", f"0x{word:08x}", "unknown", known=False)

    btarget = (addr + 4 + (simm << 2)) & 0xFFFFFFFF

    def memop(mn, treg, cat="mem", **kw):
        return I(mn, f"{treg}, {simm}({r(rs)})", cat, **kw)

    if op == 0:
        if word == 0:
            return I("nop")
        if fn in _SH_IMM:
            return I(_SH_IMM[fn], f"{r(rd)}, {r(rt)}, {sa}")
        if fn in _SH_VAR:
            return I(_SH_VAR[fn], f"{r(rd)}, {r(rt)}, {r(rs)}")
        if fn in _RD_RS_RT:
            return I(_RD_RS_RT[fn], f"{r(rd)}, {r(rs)}, {r(rt)}")
        if fn in (24, 25):
            ops = f"{r(rs)}, {r(rt)}" if rd == 0 else f"{r(rd)}, {r(rs)}, {r(rt)}"
            return I(_RS_RT[fn], ops)
        if fn in _RS_RT:
            return I(_RS_RT[fn], f"{r(rs)}, {r(rt)}", "system" if fn >= 48 else "alu")
        if fn == 8:
            return I("jr", r(rs), "jump", kind="return" if rs == 31 else "indirect_jump")
        if fn == 9:
            ops = r(rs) if rd == 31 else f"{r(rd)}, {r(rs)}"
            return I("jalr", ops, "jump", kind="indirect_call")
        if fn == 12:
            return I("syscall", "", "syscall", kind="syscall")
        if fn == 13:
            return I("break", "", "system")
        if fn == 15:
            return I("sync", "", "system")
        if fn == 16:
            return I("mfhi", r(rd))
        if fn == 17:
            return I("mthi", r(rs))
        if fn == 18:
            return I("mflo", r(rd))
        if fn == 19:
            return I("mtlo", r(rs))
        if fn == 40:
            return I("mfsa", r(rd), ps2_specific=True)
        if fn == 41:
            return I("mtsa", r(rs), ps2_specific=True)
        return unk()
    if op == 1:
        if rt in _REGIMM:
            mn = _REGIMM[rt]
            return I(mn, f"{r(rs)}, 0x{btarget:08x}", "branch",
                     kind="call" if rt >= 16 else "branch", likely=mn.endswith("l"),
                     branch_target=btarget)
        if rt == 24:
            return I("mtsab", f"{r(rs)}, {simm}", ps2_specific=True)
        if rt == 25:
            return I("mtsah", f"{r(rs)}, {simm}", ps2_specific=True)
        return unk()
    if op in (2, 3):
        t = ((addr + 4) & 0xF0000000) | ((word & 0x3FFFFFF) << 2)
        return I("j" if op == 2 else "jal", f"0x{t:08x}", "jump",
                 kind="jump" if op == 2 else "call", jump_target=t)
    if op in _BR2:
        mn = _BR2[op]
        return I(mn, f"{r(rs)}, {r(rt)}, 0x{btarget:08x}", "branch", kind="branch",
                 likely=mn.endswith("l"), branch_target=btarget)
    if op in _BR1:
        mn = _BR1[op]
        return I(mn, f"{r(rs)}, 0x{btarget:08x}", "branch", kind="branch",
                 likely=mn.endswith("l"), branch_target=btarget)
    if op in _IMM_SIGNED:
        return I(_IMM_SIGNED[op], f"{r(rt)}, {r(rs)}, {simm}")
    if op in _IMM_LOGIC:
        return I(_IMM_LOGIC[op], f"{r(rt)}, {r(rs)}, 0x{imm:x}")
    if op == 15:
        return I("lui", f"{r(rt)}, 0x{imm:x}")
    if op in _MEM:
        return memop(_MEM[op], r(rt), ps2_specific=op in (30, 31))
    if op == 47:
        return I("cache", f"{rt}, {simm}({r(rs)})", "system")
    if op == 51:
        return I("pref", f"{rt}, {simm}({r(rs)})", "system")
    if op == 49:
        return memop("lwc1", f"$f{rt}", "fpu")
    if op == 57:
        return memop("swc1", f"$f{rt}", "fpu")
    if op == 54:
        return memop("lqc2", f"$vf{rt}", "vu0", ps2_specific=True)
    if op == 62:
        return memop("sqc2", f"$vf{rt}", "vu0", ps2_specific=True)
    if op == 16:  # COP0
        if rs == 0:
            return I("mfc0", f"{r(rt)}, $c0_{rd}", "cop0")
        if rs == 4:
            return I("mtc0", f"{r(rt)}, $c0_{rd}", "cop0")
        if rs == 8 and rt in _BCCOND:
            return I("bc0" + _BCCOND[rt], f"0x{btarget:08x}", "branch", kind="branch",
                     likely=rt >= 2, branch_target=btarget)
        if rs == 16:
            names = {1: "tlbr", 2: "tlbwi", 6: "tlbwr", 8: "tlbp", 24: "eret", 56: "ei", 57: "di"}
            if fn in names:
                return I(names[fn], "", "cop0")
        return unk()
    if op == 17:  # COP1
        if rs == 0:
            return I("mfc1", f"{r(rt)}, $f{rd}", "fpu")
        if rs == 2:
            return I("cfc1", f"{r(rt)}, $fcr{rd}", "fpu")
        if rs == 4:
            return I("mtc1", f"{r(rt)}, $f{rd}", "fpu")
        if rs == 6:
            return I("ctc1", f"{r(rt)}, $fcr{rd}", "fpu")
        if rs == 8 and rt in _BCCOND:
            return I("bc1" + _BCCOND[rt], f"0x{btarget:08x}", "branch", kind="branch",
                     likely=rt >= 2, branch_target=btarget)
        if rs == 16 and fn in _COP1_S:
            return I(_COP1_S[fn], f"$f{sa}, $f{rd}, $f{rt}", "fpu")
        if rs == 20 and fn == 32:
            return I("cvt.s.w", f"$f{sa}, $f{rd}", "fpu")
        return unk()
    if op == 18:  # COP2 / VU0
        if rs == 1:
            return I("qmfc2", f"{r(rt)}, $vf{rd}", "vu0", ps2_specific=True)
        if rs == 2:
            return I("cfc2", f"{r(rt)}, $vi{rd}", "vu0", ps2_specific=True)
        if rs == 5:
            return I("qmtc2", f"{r(rt)}, $vf{rd}", "vu0", ps2_specific=True)
        if rs == 6:
            return I("ctc2", f"{r(rt)}, $vi{rd}", "vu0", ps2_specific=True)
        if rs == 8 and rt in _BCCOND:
            return I("bc2" + _BCCOND[rt], f"0x{btarget:08x}", "branch", kind="branch",
                     likely=rt >= 2, branch_target=btarget, ps2_specific=True)
        if rs >= 16:
            return I("vu0_macro", f"funct=0x{(word & 0x3F):02x} (decodificação genérica)",
                     "vu0", ps2_specific=True)
        return unk()
    if op == 28:  # MMI
        if fn in _MMI_TOP:
            mn = _MMI_TOP[fn]
            if mn in ("mfhi1", "mflo1"):
                ops = r(rd)
            elif mn in ("mthi1", "mtlo1"):
                ops = r(rs)
            elif mn in ("psllh", "psrlh", "psrah", "psllw", "psrlw", "psraw"):
                ops = f"{r(rd)}, {r(rt)}, {sa}"
            elif mn == "plzcw":
                ops = f"{r(rd)}, {r(rs)}"
            else:
                ops = f"{r(rd)}, {r(rs)}, {r(rt)}"
            return I(mn, ops, "mmi", ps2_specific=True)
        sub = {8: _MMI0, 40: _MMI1, 9: _MMI2, 41: _MMI3}.get(fn)
        if sub is not None and sa in sub:
            return I(sub[sa], f"{r(rd)}, {r(rs)}, {r(rt)}", "mmi", ps2_specific=True)
        if fn in (48, 49) and sa in _PMFHL:
            mn = ("pmfhl." if fn == 48 else "pmthl.") + _PMFHL[sa]
            return I(mn, r(rd) if fn == 48 else r(rs), "mmi", ps2_specific=True)
        return unk()
    return unk()
