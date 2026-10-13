"""Geração do pacote (FASE 7).

Só marca algo como "nativo" se `port_level == 3`. No protótipo isso nunca ocorre. O pacote
produzido contém o relatório e o código C traduzido: é um PACOTE DE ANÁLISE/PROTÓTIPO.
Nenhum recurso do jogo (assets comerciais) é copiado — respeita direitos autorais.
"""
from __future__ import annotations

import json
import os
from typing import List

from .analysis import ElfAnalysis
from .report import to_json, to_markdown
from .translator import RUNTIME_HEADER, generate_c_unit

CLASSIFICACAO = {
    0: "ANALISE_APENAS",
    1: "TRADUCAO_PARCIAL_NAO_EXECUTAVEL",
    2: "CODIGO_TRADUZIDO_SEM_RUNTIME_DE_HARDWARE",
    3: "CANDIDATO_NATIVO",
}


def can_package(a: ElfAnalysis) -> bool:
    return any(f.status == "translated" for f in a.functions)


def build_package(a: ElfAnalysis, out_dir: str, include_partial: bool = False) -> List[str]:
    if not can_package(a):
        raise ValueError("Nenhuma função foi traduzida por completo; não há o que empacotar.")
    os.makedirs(out_dir, exist_ok=True)
    written = []

    def w(name: str, text: str) -> None:
        p = os.path.join(out_dir, name)
        with open(p, "w", encoding="utf-8", newline="\n") as f:
            f.write(text)
        written.append(p)

    w("ps2rt.h", RUNTIME_HEADER)
    w("functions.c", generate_c_unit(a.functions, only_translated=not include_partial))
    w("report.json", to_json(a))
    w("report.md", to_markdown(a))
    w("STATUS.txt",
      f"Classificação: {CLASSIFICACAO[a.port_level]}\n"
      f"Nível: {a.port_level}/3 — {a.port_label}\n"
      "Este pacote NÃO contém um jogo nativo executável. Contém código C gerado para as funções\n"
      "com semântica verificada e um runtime mínimo (CPU+memória). GS, VU, áudio, IOP e kernel\n"
      "NÃO estão implementados. Assets do jogo não são incluídos.\n"
      + "\n".join(f"- {n}" for n in a.port_notes) + "\n")
    return written
