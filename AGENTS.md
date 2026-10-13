# Instruções para agentes de IA (Copilot, Codex, Claude, etc.)

Projeto: **PS2Native** — análise e portabilidade experimental de jogos de PS2 (ISO → ELF → R5900 → C).
Leia primeiro: `README.md`, `docs/ARQUITETURA.md`, `docs/PESQUISA.md`, `docs/ROADMAP.md`.

## Regras inegociáveis
1. **Honestidade**: nunca declare "nativo", "funciona" ou "compatível" sem execução e testes que provem.
   O nível 3 de `port_status()` só pode ser alcançado com backends reais (`implemented = True`).
2. **Nada de ignorar instrução desconhecida.** Sem semântica implementada → `ir.Unsupported(motivo)`,
   registro no relatório e `ps2_unsupported()` no C gerado.
3. **Toda nova instrução traduzida exige teste diferencial** em `tests/test_translation.py`
   (C compilado × executor Python de `tests/helpers.py`), incluindo valores de borda.
4. **Sem material comercial**: não adicione ISOs, BIOS, assets ou binários de jogos. Testes usam só `ps2native/testgen.py`.
5. **Licenças**: não copie código de PS2Recomp/PCSX2 (GPL-3.0) nem de outros projetos sem verificar compatibilidade.
   Cite fontes em `docs/PESQUISA.md` e marque o que não foi verificado como **[verificar]**.
6. Se depender de emular CPU/hardware do PS2, classifique como "solução baseada em emulação".
7. Documentação e UI em **português**. Código/identificadores podem seguir o padrão atual.

## Como validar qualquer mudança
```bash
python -m unittest discover -s tests -t . -v   # tem que passar; núcleo não precisa de PySide6
```
Testes de semântica precisam de gcc/clang (no CI Linux há). Não remova testes para "passar".

## Mapa do código
`mips.py` decodifica · `ir.py` lift/IR/interpretador/emissor C · `translator.py` funções e fluxo ·
`analysis.py` pipeline · `elf.py`/`iso9660.py` formatos · `interfaces.py` contratos de hardware ·
`package.py` pacote · `cli.py`/`gui.py` interfaces.

## Como trabalhar
Pegue uma tarefa de `docs/ROADMAP.md`, abra PR pequeno, atualize README/ARQUITETURA se mudar limites,
e atualize a lista de limitações conhecidas. Uma tarefa por PR.
