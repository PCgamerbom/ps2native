import io
import unittest

from ps2native import testgen
from ps2native.elf import ElfError, parse_elf
from ps2native.formats import identify
from ps2native.iso9660 import IsoError, IsoImage, parse_system_cnf


class TestElf(unittest.TestCase):
    def setUp(self):
        words, syms = testgen.demo_program()
        self.elf = parse_elf(testgen.build_elf(words, symbols=syms))

    def test_header(self):
        self.assertEqual(self.elf.entry, testgen.BASE)
        self.assertTrue(self.elf.looks_like_ee)
        self.assertEqual(len(self.elf.segments), 1)
        self.assertTrue(self.elf.segments[0].executable)

    def test_sections_and_symbols(self):
        self.assertIn(".text", [s.name for s in self.elf.sections])
        names = {s.name: s.value for s in self.elf.symbols}
        self.assertEqual(names["add"], testgen.ADDR_ADD)
        self.assertEqual(len(names), 5)

    def test_read32(self):
        self.assertEqual(self.elf.read32(testgen.ADDR_ADD), testgen.addu(testgen.V0, testgen.A0, testgen.A1))
        self.assertIsNone(self.elf.read32(0x10))

    def test_invalid(self):
        with self.assertRaises(ElfError):
            parse_elf(b"not an elf" * 10)
        words, syms = testgen.demo_program()
        data = testgen.build_elf(words, symbols=syms)
        with self.assertRaises(ElfError):
            parse_elf(data[:0x90])  # PT_LOAD truncado

    def test_irx(self):
        words, _ = testgen.demo_program()
        e = parse_elf(testgen.build_elf(words, e_type=0xFF80))
        self.assertIn("IRX", e.kind)


class TestIso(unittest.TestCase):
    def check(self, raw):
        iso = IsoImage(io.BytesIO(testgen.demo_iso(raw)))
        entries = iso.walk()
        paths = [e.path for e in entries]
        self.assertEqual(paths, ["/DATA", "/DATA/TEST.VAG", "/SLUS_999.99", "/SYSTEM.CNF"])
        self.assertEqual(iso.volume_id, "PS2NATIVE_DEMO")
        cnf = parse_system_cnf(iso.read_file(iso.find("/SYSTEM.CNF", entries)).decode())
        self.assertEqual(cnf.boot_path, "/SLUS_999.99")
        self.assertEqual(cnf.platform, "PlayStation 2")
        self.assertEqual(iso.read_file(iso.find("/DATA/TEST.VAG", entries))[:4], b"VAGp")
        self.assertEqual(iso.read_file(iso.find("/SLUS_999.99", entries))[:4], b"\x7fELF")
        return iso

    def test_cooked(self):
        self.assertEqual(self.check(False).sector_size, 2048)

    def test_raw_2352(self):
        iso = self.check(True)
        self.assertEqual((iso.sector_size, iso.data_offset), (2352, 16))

    def test_invalid(self):
        with self.assertRaises(IsoError):
            IsoImage(io.BytesIO(b"\0" * 100000))

    def test_cnf_parsing(self):
        c = parse_system_cnf("BOOT2 = cdrom0:\\SLES_123.45;1\r\nVER = 1.00\r\n")
        self.assertEqual(c.boot_path, "/SLES_123.45")
        self.assertEqual(parse_system_cnf("BOOT = cdrom:\\SLPS_000.01;1").platform, "PlayStation 1")


class TestFormats(unittest.TestCase):
    def test_known_asset_signatures(self):
        self.assertEqual(identify(b"HCA\x00"), "HCA (áudio CRI)")
        self.assertEqual(identify(b"RNC\x01"), "RNC (dados comprimidos, método 1)")
        self.assertEqual(identify(b"CRILAYLA"), "CRILAYLA (dados comprimidos CRI)")
        self.assertEqual(identify(b"RIFF" + b"\x00" * 4 + b"WAVE"), "WAVE (áudio RIFF)")
        self.assertEqual(identify(b"BOOT2 = cdrom0:\\SLUS_000.00;1", "/SYSTEM.CNF"),
                         "SYSTEM.CNF (configuração de boot, inferido pelo nome)")

    def test_extension_guess_is_explicit(self):
        self.assertEqual(identify(b"unknown", "SOUND.ADX"), "ADX (provável, inferido pela extensão)")
        self.assertIsNone(identify(b"unknown", "DATA.BIN"))


if __name__ == "__main__":
    unittest.main()
