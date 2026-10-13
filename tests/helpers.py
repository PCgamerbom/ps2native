import os
import random
import shutil
import subprocess
import tempfile

from ps2native import ir
from ps2native.mips import decode
from ps2native.translator import RUNTIME_HEADER, generate_c_unit, translate_function

CC = shutil.which("gcc") or shutil.which("cc") or shutil.which("clang")
BASE = 0x00100000


def reader(words, base=BASE):
    mem = {base + 4 * i: w & 0xFFFFFFFF for i, w in enumerate(words)}
    return mem.get


def run_reference(read32, entry, st, max_steps=100000):
    """Executor de referência INDEPENDENTE do tradutor C: segue o fluxo (delay slots) em Python
    e usa o interpretador do IR para a semântica das instruções."""
    pc = entry
    steps = 0
    while steps < max_steps:
        steps += 1
        ins = decode(read32(pc), pc)
        if ins.kind in ("branch", "jump", "return"):
            slot = decode(read32(pc + 4), pc + 4)
            if ins.kind == "branch":
                taken = ir.eval_expr(ir.cond_expr(ins), st)
                target = ins.branch_target
            elif ins.kind == "jump":
                taken, target = 1, ins.jump_target
            else:
                taken, target = 1, None
            for s in ir.lift(slot):
                ir.exec_stmt(s, st)
            if ins.kind == "return":
                return
            pc = target if taken else pc + 8
            continue
        for s in ir.lift(ins):
            ir.exec_stmt(s, st)
        pc += 4
    raise RuntimeError("limite de passos")


DRIVER = r"""
#include <string.h>
#include "ps2rt.h"
void %(fn)s(PS2Ctx *c);
int main(void) {
    uint8_t *mem = calloc(1, PS2_MEM_MASK + 1);
    unsigned long long a, b;
    while (scanf("%%llx %%llx", &a, &b) == 2) {
        PS2Ctx c; memset(&c, 0, sizeof c); c.mem = mem;
        memset(mem, 0, 0x2000);
        c.r[4] = a; c.r[5] = b; c.r[22] = 0x1234; c.r[23] = 0x5678; c.r[29] = 0x8000;
        %(fn)s(&c);
        for (int i = 1; i < 32; i++) printf("%%016llx ", (unsigned long long)c.r[i]);
        printf("%%016llx %%016llx\n", (unsigned long long)c.hi, (unsigned long long)c.lo);
    }
    return 0;
}
"""


def compile_run(results, entry, inputs):
    """Compila o C gerado com gcc e executa `entry` para cada (a,b). Retorna lista de linhas."""
    d = tempfile.mkdtemp()
    try:
        for name, text in (("ps2rt.h", RUNTIME_HEADER), ("functions.c", generate_c_unit(results)),
                           ("driver.c", DRIVER % {"fn": "ps2_func_%08X" % entry})):
            with open(os.path.join(d, name), "w", encoding="utf-8") as f:
                f.write(text)
        exe = os.path.join(d, "t")
        subprocess.run([CC, "-O1", "-w", "-o", exe, os.path.join(d, "functions.c"),
                        os.path.join(d, "driver.c"), "-I", d], check=True, capture_output=True)
        inp = "".join("%x %x\n" % (a & ((1 << 64) - 1), b & ((1 << 64) - 1)) for a, b in inputs)
        out = subprocess.run([exe], input=inp, text=True, capture_output=True, check=True).stdout
        return out.strip().split("\n")
    finally:
        shutil.rmtree(d, ignore_errors=True)


def reference_lines(read32, entry, inputs, mem_size=1 << 25):
    lines = []
    for a, b in inputs:
        st = ir.State(mem_size)
        st.r[4], st.r[5] = a & ir.M64, b & ir.M64
        st.r[22], st.r[23], st.r[29] = 0x1234, 0x5678, 0x8000
        run_reference(read32, entry, st)
        lines.append(" ".join("%016x" % st.r[i] for i in range(1, 32)) + " %016x %016x" % (st.hi, st.lo))
    return lines


def rand_inputs(n, seed=1234):
    rng = random.Random(seed)
    special = [0, 1, -1, 0x7FFFFFFF, 0x80000000, 0xFFFFFFFF, 0x80000001, 5, 31, 32]
    vals = special + [rng.getrandbits(32) for _ in range(20)] + [rng.getrandbits(64) for _ in range(10)]
    pairs = [(a, b) for a in special for b in special]
    pairs += [(rng.choice(vals), rng.choice(vals)) for _ in range(n)]
    return pairs
