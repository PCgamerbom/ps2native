"""Exportação de relatórios (JSON e Markdown)."""
from __future__ import annotations

import json
from typing import Optional

from .analysis import ElfAnalysis, IsoReport

DISCLAIMER = ("**Este relatório descreve uma ANÁLISE. Desmontar não é recuperar código-fonte, "
              "e nenhum resultado aqui deve ser lido como \"jogo funcionando nativamente\".**")


def to_json(obj) -> str:
    return json.dumps(obj.to_dict(), indent=2, ensure_ascii=False)


def _elf_md(a: ElfAnalysis) -> str:
    L = ["## Executável (ELF)", "",
         f"- Tipo: {a.kind}", f"- Parece EE (heurística): {'sim' if a.looks_like_ee else 'não'}",
         f"- Entry point: `0x{a.entry:08x}`", f"- SHA-256: `{a.sha256}`", f"- Tamanho: {a.size} bytes",
         f"- Símbolos: {a.n_symbols}", f"- Instruções (palavras em segmentos executáveis): {a.n_instructions}",
         f"- Palavras não decodificadas: {a.unknown_words}", ""]
    L += ["### Segmentos", "", "| vaddr | filesz | memsz | flags |", "|---|---|---|---|"]
    L += [f"| {s['vaddr']} | {s['filesz']} | {s['memsz']} | {s['flags']} |" for s in a.segments]
    L += ["", "### Categorias de instrução", ""]
    L += [f"- {k}: {v}" for k, v in sorted(a.categories.items(), key=lambda kv: -kv[1])]
    L += ["", "### Instruções específicas do PS2 encontradas", ""]
    L += [f"- {k}: {v}" for k, v in sorted(a.ps2_specific.items(), key=lambda kv: -kv[1])] or ["- (nenhuma)"]
    L += ["", "### Referências a hardware (heurística por `lui`)", ""]
    L += [f"- `{h['region']}` — {h['description']} (primeira em {h['first_at']}, {h['count']}x)"
          for h in a.hardware_refs] or ["- (nenhuma detectada)"]
    L += ["", "### Syscalls", ""]
    L += [f"- {s['addr']}: syscall #{s['number'] if s['number'] is not None else '?'}" for s in a.syscalls] or ["- (nenhuma)"]
    L += ["", f"### Funções ({len(a.functions)})", "", "| entrada | nome | insn | status | não suportadas |", "|---|---|---|---|---|"]
    for f in a.functions[:500]:
        L.append(f"| 0x{f.entry:08x} | {f.name} | {f.n_insns} | {f.status} | {f.n_unsupported} |")
    if len(a.functions) > 500:
        L.append(f"| … | +{len(a.functions) - 500} funções (veja o JSON) | | | |")
    L += ["", "### Instruções/funções NÃO suportadas (agregado)", ""]
    L += [f"- {k}: {v}x" for k, v in list(a.unsupported_summary.items())[:50]] or ["- (nenhuma)"]
    L += ["", "## Status da portabilidade", "",
          f"- **Nível {a.port_level}/3: {a.port_label}**",
          f"- Instruções traduzidas dentro das funções descobertas: {a.translated_pct}%"]
    L += [f"- {n}" for n in a.port_notes]
    L += ["", "### Premissas do tradutor", ""] + [f"- {x}" for x in a.assumptions]
    return "\n".join(L)


def to_markdown(obj) -> str:
    if isinstance(obj, ElfAnalysis):
        return "# Relatório PS2Native (ELF)\n\n" + DISCLAIMER + "\n\n" + _elf_md(obj) + "\n"
    r: IsoReport = obj
    L = ["# Relatório PS2Native (ISO)", "", DISCLAIMER, "", "## Imagem", "",
         f"- Arquivo: `{r.path}`", f"- Plataforma (SYSTEM.CNF): {r.platform}",
         f"- System ID: {r.system_id}", f"- Volume ID: {r.volume_id}",
         f"- Layout: {r.sector_layout}", f"- Tamanho: {r.total_size} bytes",
         f"- Arquivos: {r.n_files} | Diretórios: {r.n_dirs}",
         f"- Boot ({r.boot_key}): `{r.boot_path}`", ""]
    if r.warnings:
        L += ["### Avisos", ""] + [f"- {w}" for w in r.warnings] + [""]
    L += ["### SYSTEM.CNF", ""] + [f"- {k} = {v}" for k, v in r.system_cnf.items()]
    L += ["", "### Executáveis/módulos encontrados", ""]
    L += [f"- `{e['path']}` — {e['format']} — {e['size']} bytes" for e in r.executables] or ["- (nenhum)"]
    L += ["", "### Todos os arquivos", "", "| caminho | tamanho | formato |", "|---|---|---|"]
    L += [f"| {f['path']} | {f['size']} | {f['format'] or 'Não identificado'} |" for f in r.files[:2000]]
    if r.elf:
        L += ["", _elf_md(r.elf)]
    return "\n".join(L) + "\n"
