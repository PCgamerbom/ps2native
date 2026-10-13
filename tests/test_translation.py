import unittest

from ps2native import ir, testgen as g
from ps2native.translator import generate_c_unit, translate_function
from tests.helpers import BASE, CC, compile_run, rand_inputs, reader, reference_lines, run_reference


def alu_mix():
    return [
        g.addu(8, g.A0, g.A1), g.subu(9, g.A0, g.A1), g.xor_(10, g.A0, g.A1), g.nor(11, g.A0, g.A1),
        g.slt(g.V0, g.A0, g.A1), g.sltu(g.V1, g.A0, g.A1), g.sll(g.A2, g.A0, 3), g.sra(g.A3, g.A1, 5),
        g.srl(12, g.A1, 7), g.mult(g.A0, g.A1), g.mflo(13), g.mfhi(14), g.sllv(15, g.A0, g.A1),
        g.srav(24, g.A0, g.A1), g.slti(16, g.A0, -5), g.sltiu(17, g.A0, -5), g.andi(18, g.A1, 0xFFF0),
        g.ori(19, g.A0, 0x8001), g.xori(20, g.A1, 0xF0F0), g.lui(21, 0x8000), g.movz(22, g.A0, g.A1),
        g.movn(23, g.A0, g.A1), g.multu(g.A0, g.A1), g.mflo(25), g.mfhi(28), g.jr(g.RA), g.NOP]


def mem_variants():
    return [g.sw(g.A0, 0, g.A1), g.lb(8, 0, g.A1), g.lbu(9, 0, g.A1), g.lh(10, 0, g.A1),
            g.lhu(11, 0, g.A1), g.lw(12, 0, g.A1), g.sb(g.A0, 8, g.A1), g.sh(g.A0, 12, g.A1),
            g.lw(13, 8, g.A1), g.lw(14, 12, g.A1), g.jr(g.RA), g.NOP]


def loop_sum():
    words, _ = g.demo_program()
    off = (g.ADDR_LOOP - BASE) // 4
    return off, words


@unittest.skipUnless(CC, "sem compilador C disponível")
class TestSemantics(unittest.TestCase):
    """Compara o C gerado (compilado com gcc) com o executor de referência em Python."""

    def run_case(self, words, inputs, entry=BASE):
        rd = reader(words)
        res = translate_function(rd, entry)
        self.assertEqual(res.status, "translated", res.unsupported)
        got = compile_run([res], entry, inputs)
        want = reference_lines(rd, entry, inputs)
        self.assertEqual(len(got), len(want))
        for i, (x, y) in enumerate(zip(got, want)):
            self.assertEqual(x, y, f"divergência na entrada {inputs[i]}")

    def test_alu_mix(self):
        self.run_case(alu_mix(), rand_inputs(150))

    def test_loads_stores(self):
        ins = [(v, 0x1000) for v in (0, 0x80, 0x8000, 0x80808080, 0xFFFFFFFF, 0x12345678, 0xDEADBEEFCAFEBABE)]
        self.run_case(mem_variants(), ins)

    def test_loop_with_delay_slots(self):
        words, _ = g.demo_program()
        entry = g.ADDR_LOOP
        rd = reader(words)
        res = translate_function(rd, entry)
        self.assertEqual(res.status, "translated")
        inputs = [(n, 0) for n in range(0, 12)]
        got = compile_run([res], entry, inputs)
        for (n, _), line in zip(inputs, got):
            v0 = int(line.split()[1], 16)  # r[2]
            self.assertEqual(v0, n * (n + 1) // 2)
        self.assertEqual(got, reference_lines(rd, entry, inputs))

    def test_call_and_return(self):
        words, _ = g.demo_program()
        caller = [g.addiu(g.SP, g.SP, -16), g.sw(g.RA, 0, g.SP), g.addiu(g.A0, g.Z, 5),
                  g.jal(g.ADDR_ADD), g.addiu(g.A1, g.Z, 7), g.lw(g.RA, 0, g.SP), g.jr(g.RA),
                  g.addiu(g.SP, g.SP, 16)]
        full = list(words)
        # coloca o caller em 0x100100
        while len(full) < 0x40:
            full.append(0)
        full += caller
        rd = reader(full)
        entry = BASE + 4 * 0x40
        r1 = translate_function(rd, entry)
        r2 = translate_function(rd, g.ADDR_ADD)
        self.assertEqual((r1.status, r2.status), ("translated", "translated"))
        self.assertEqual(r1.calls, [g.ADDR_ADD])
        out = compile_run([r1, r2], entry, [(0, 0)])[0].split()
        self.assertEqual(int(out[1], 16), 12)           # v0 = 5 + 7
        self.assertEqual(int(out[28], 16), 0x8000)       # sp restaurado (r[29] -> índice 28)


class TestHonesty(unittest.TestCase):
    def test_unsupported_never_silent(self):
        words, _ = g.demo_program()
        rd = reader(words)
        res = translate_function(rd, g.ADDR_PS2)
        self.assertEqual(res.status, "partial")
        self.assertEqual({u["mnemonic"] for u in res.unsupported}, {"pand", "lq", "qmtc2"})
        self.assertGreaterEqual(res.c_source.count("ps2_unsupported("), 3)
        for u in res.unsupported:
            self.assertTrue(u["reason"])

    def test_unknown_word_is_unsupported(self):
        res = translate_function(reader([0x74000000, g.jr(g.RA), g.NOP]), BASE)
        self.assertEqual(res.status, "partial")
        self.assertIn("desconhecido", res.unsupported[0]["reason"])

    def test_syscall_and_indirect_jump(self):
        res = translate_function(reader([g.syscall(), g.jr(8), g.NOP, g.jr(g.RA), g.NOP]), BASE)
        reasons = " ".join(u["reason"] for u in res.unsupported)
        self.assertIn("syscall", reasons)
        self.assertIn("indireta", reasons)
        self.assertNotEqual(res.status, "translated")

    def test_div_not_translated(self):
        res = translate_function(reader([g.div(g.A0, g.A1), g.jr(g.RA), g.NOP]), BASE)
        self.assertEqual(res.unsupported[0]["mnemonic"], "div")

    def test_branch_with_branch_in_delay_slot(self):
        res = translate_function(reader([g.beq(0, 0, 2), g.beq(0, 0, 1), g.NOP, g.jr(g.RA), g.NOP]), BASE)
        self.assertNotEqual(res.status, "translated")

    def test_ir_interpreter_known_values(self):
        st = ir.State(1 << 16)
        st.r[4], st.r[5] = 0xFFFFFFFF, 2
        for s in ir.lift(__import__("ps2native.mips", fromlist=["decode"]).decode(g.addu(2, 4, 5))):
            ir.exec_stmt(s, st)
        self.assertEqual(st.r[2], 1)  # 32-bit wrap + sign-extend
        st.r[4] = 0x80000000
        for s in ir.lift(__import__("ps2native.mips", fromlist=["decode"]).decode(g.sra(3, 4, 4))):
            ir.exec_stmt(s, st)
        self.assertEqual(st.r[3], 0xFFFFFFFFF8000000)


if __name__ == "__main__":
    unittest.main()
