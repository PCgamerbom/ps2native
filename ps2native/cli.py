"""Interface de linha de comando: `python -m ps2native ...`"""
from __future__ import annotations

import argparse
import os
import sys

from .analysis import analyze_elf, analyze_iso
from .package import build_package, can_package
from .report import to_json, to_markdown


def _progress(stage: str, pct: int) -> None:
    print(f"[{pct:3d}%] {stage}", file=sys.stderr)


def main(argv=None) -> int:
    p = argparse.ArgumentParser(prog="ps2native", description="PS2Native — análise experimental")
    sub = p.add_subparsers(dest="cmd", required=True)
    a = sub.add_parser("analyze", help="analisa uma ISO de PS2")
    a.add_argument("iso")
    a.add_argument("-o", "--out", help="pasta de saída (relatórios)")
    a.add_argument("--package", action="store_true", help="gera pacote de análise/protótipo")
    e = sub.add_parser("analyze-elf", help="analisa um ELF diretamente")
    e.add_argument("elf")
    e.add_argument("-o", "--out")
    e.add_argument("--package", action="store_true")
    sub.add_parser("gui", help="abre a interface gráfica (requer PySide6)")
    d = sub.add_parser("make-demo-iso", help="gera uma ISO de demonstração PRÓPRIA (não comercial)")
    d.add_argument("output")
    d.add_argument("--raw", action="store_true", help="setores de 2352 bytes")
    args = p.parse_args(argv)

    if args.cmd == "gui":
        from .gui import run
        return run()

    if args.cmd == "make-demo-iso":
        from .testgen import demo_iso
        with open(args.output, "wb") as f:
            f.write(demo_iso(args.raw))
        print("ISO de demonstração gerada:", args.output, file=sys.stderr)
        return 0

    if args.cmd == "analyze":
        rep = analyze_iso(args.iso, _progress)
        elf = rep.elf
        report_obj = rep
    else:
        with open(args.elf, "rb") as f:
            elf = analyze_elf(f.read(), _progress)
        report_obj = elf

    md = to_markdown(report_obj)
    print(md)
    if args.out:
        os.makedirs(args.out, exist_ok=True)
        with open(os.path.join(args.out, "report.md"), "w", encoding="utf-8") as f:
            f.write(md)
        with open(os.path.join(args.out, "report.json"), "w", encoding="utf-8") as f:
            f.write(to_json(report_obj))
    if args.package:
        if elf is None or not can_package(elf):
            print("Sem funções traduzidas por completo: pacote não gerado.", file=sys.stderr)
            return 2
        out = os.path.join(args.out or ".", "package")
        for path in build_package(elf, out):
            print("gerado:", path, file=sys.stderr)
    return 0
