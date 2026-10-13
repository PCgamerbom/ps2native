import json
import os
import tempfile
import unittest

from ps2native import testgen
from ps2native.analysis import analyze_elf, analyze_iso, port_status
from ps2native.cli import main as cli_main
from ps2native.interfaces import adapters_ready, default_backends, get_adapter
from ps2native.package import build_package, can_package
from ps2native.report import to_json, to_markdown
from ps2native.translator import FuncResult


class TestAnalysis(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.TemporaryDirectory()
        cls.iso_path = os.path.join(cls.tmp.name, "demo.iso")
        with open(cls.iso_path, "wb") as f:
            f.write(testgen.demo_iso())
        cls.rep = analyze_iso(cls.iso_path)

    @classmethod
    def tearDownClass(cls):
        cls.tmp.cleanup()

    def test_iso_report(self):
        r = self.rep
        self.assertEqual(r.platform, "PlayStation 2")
        self.assertEqual(r.boot_path, "/SLUS_999.99")
        self.assertEqual(r.main_executable["path"], "/SLUS_999.99")
        self.assertEqual([e["path"] for e in r.executables], ["/SLUS_999.99"])
        self.assertEqual(r.n_files, 3)
        self.assertEqual(r.warnings, [])

    def test_elf_findings(self):
        a = self.rep.elf
        st = {f.name: f.status for f in a.functions}
        self.assertEqual(st, {"main": "partial", "add": "translated", "loop_sum": "translated",
                              "ps2_stuff": "partial", "mem_roundtrip": "translated"})
        self.assertEqual(a.syscalls, [{"addr": "0x00100020", "number": 60}])
        self.assertEqual(len(a.hardware_refs), 1)
        self.assertIn("GS", a.hardware_refs[0]["description"])
        self.assertEqual(a.ps2_specific, {"pand": 1, "lq": 1, "qmtc2": 1})
        self.assertEqual(a.unknown_words, 0)

    def test_never_claims_native(self):
        a = self.rep.elf
        self.assertLess(a.port_level, 3)
        md = to_markdown(self.rep)
        self.assertIn("NÃO é um port nativo completo", md)

    def test_port_status_requires_everything(self):
        ok = FuncResult(0, 4, 1, "translated")
        self.assertEqual(port_status([ok], [])[0], 2)           # traduzido, mas sem runtime
        self.assertEqual(port_status([ok], [{"x": 1}], True)[0], 2)  # hardware pendente
        self.assertEqual(port_status([ok], [], True)[0], 3)     # só com adaptadores reais
        bad = FuncResult(0, 4, 1, "partial")
        self.assertEqual(port_status([ok, bad], [], True)[0], 1)
        self.assertEqual(port_status([], [])[0], 0)

    def test_default_backends_not_ready(self):
        b = default_backends()
        self.assertFalse(adapters_ready(b))
        with self.assertRaises(NotImplementedError):
            b["renderer"].present()
        self.assertIsNotNone(get_adapter("DEMO_000.00"))

    def test_json_roundtrip(self):
        d = json.loads(to_json(self.rep))
        self.assertEqual(d["elf"]["functions_total"], 5)
        self.assertEqual(d["elf"]["entry"], "0x00100000")

    def test_package(self):
        a = self.rep.elf
        self.assertTrue(can_package(a))
        out = os.path.join(self.tmp.name, "pkg")
        files = build_package(a, out)
        names = {os.path.basename(f) for f in files}
        self.assertEqual(names, {"ps2rt.h", "functions.c", "report.json", "report.md", "STATUS.txt"})
        status = open(os.path.join(out, "STATUS.txt"), encoding="utf-8").read()
        self.assertIn("NÃO contém um jogo nativo", status)
        c = open(os.path.join(out, "functions.c"), encoding="utf-8").read()
        self.assertIn("ps2_func_00100030", c)
        self.assertNotIn("ps2_func_00100060(PS2Ctx *c) {", c)  # função parcial fica fora por padrão

    def test_package_refused_without_translation(self):
        words = [testgen.syscall(), testgen.jr(testgen.RA), testgen.NOP]
        a = analyze_elf(testgen.build_elf(words))
        self.assertFalse(can_package(a))
        with self.assertRaises(ValueError):
            build_package(a, os.path.join(self.tmp.name, "nope"))

    def test_cli(self):
        out = os.path.join(self.tmp.name, "cli")
        self.assertEqual(cli_main(["analyze", self.iso_path, "-o", out, "--package"]), 0)
        self.assertTrue(os.path.exists(os.path.join(out, "package", "functions.c")))
        self.assertTrue(os.path.exists(os.path.join(out, "report.json")))

    def test_iso_without_system_cnf(self):
        p = os.path.join(self.tmp.name, "nocnf.iso")
        with open(p, "wb") as f:
            f.write(testgen.build_iso({"A.BIN": b"x" * 10}))
        r = analyze_iso(p)
        self.assertTrue(any("SYSTEM.CNF" in w for w in r.warnings))
        self.assertIsNone(r.elf)


if __name__ == "__main__":
    unittest.main()
