import unittest

from ps2native.mips import decode


class TestDecode(unittest.TestCase):
    def d(self, w, a=0x100000):
        return decode(w, a)

    def test_basic(self):
        self.assertEqual(self.d(0x27BDFFF0).text, "addiu $sp, $sp, -16")
        self.assertEqual(self.d(0x00851021).text, "addu $v0, $a0, $a1")
        self.assertEqual(self.d(0x3C081200).text, "lui $t0, 0x1200")
        self.assertEqual(self.d(0).mnemonic, "nop")
        self.assertEqual(self.d(0x8FBF0000).text, "lw $ra, 0($sp)")

    def test_control_flow(self):
        i = self.d(0x03E00008)
        self.assertEqual((i.mnemonic, i.kind), ("jr", "return"))
        self.assertEqual(self.d(0x02000008).kind, "indirect_jump")
        j = self.d(0x0C040000, 0x100000)
        self.assertEqual((j.kind, j.jump_target), ("call", 0x100000))
        b = self.d(0x10A00003, 0x100000)  # beq a1, zero, +3
        self.assertEqual(b.branch_target, 0x100010)
        self.assertTrue(b.has_delay_slot)
        self.assertTrue(self.d(0x50000001).likely)  # beql

    def test_ps2_specific(self):
        for w, mn in [(0x7BA20000, "lq"), (0x70A62089, "psllvw"), (0x70A62489, "pand")]:
            i = self.d(w)
            self.assertTrue(i.ps2_specific, mn)
        self.assertEqual(self.d(0x70A62489).mnemonic, "pand")
        self.assertEqual(self.d(0x4A000018).mnemonic, "vu0_macro")
        self.assertTrue(self.d(0x4A000018).ps2_specific)

    def test_unknown_is_flagged(self):
        i = self.d(0x74000000)  # opcode 29 não existe no R5900
        self.assertFalse(i.known)
        self.assertEqual(i.category, "unknown")

    def test_syscall(self):
        self.assertEqual(self.d(0x0000000C).kind, "syscall")


if __name__ == "__main__":
    unittest.main()
