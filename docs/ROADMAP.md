# Roadmap (tarefas para agentes/contribuidores)

Cada tarefa = 1 PR. Critério de aceite sempre inclui: `python -m unittest discover -s tests -t .` verde,
testes novos, limitações atualizadas no README.

## T1 — GPRs de 128 bits + MMI básica
Estado `uint64_t r[32][2]` (C) e `State.r` com 128 bits (Python). Implementar `lq/sq`, `pand/por/pxor/pnor`,
`paddw/psubw/paddh/paddb`, `pcpyld/pcpyud`. **Aceite:** teste diferencial para cada instrução; remover do relatório de "não suportadas".
Verificar nomes/semântica no manual do EE e no PCSX2 (só leitura, sem copiar código).

## T2 — `div/divu` e `add/sub/addi` com trap
Definir semântica de divisão por zero/overflow do R5900 a partir de fonte documentada. Trap de overflow: decidir modelo
de exceção (ex.: `ps2_trap()`), documentar. **Aceite:** testes de borda (0x80000000/-1, divisor 0).

## T3 — Branch-likely, `bltzal/bgezal`, `ld/sd` completos, `dadd*`/shifts 64-bit, `lwl/lwr/swl/swr`
**Aceite:** diferencial + casos de delay slot anulado.

## T4 — Saltos indiretos
Detectar tabelas de saltos (`jr` precedido de `lw` de tabela) e `jalr` via ponteiro de função; gerar `switch`/despacho
via tabela de funções. **Aceite:** programa de teste com jump table em `testgen.py`.

## T5 — Descoberta de funções melhor
Integrar símbolos exportados do Ghidra (JSON), separar dados de código, detectar tail calls. **Aceite:** relatório compara
funções com/sem símbolos; teste com ELF sintético.

## T6 — Syscalls/BIOS (runtime)
Tabela de syscalls do kernel do PS2 **com fonte citada**; runtime mínimo de threads/semáforos. **Aceite:** syscalls
passam de "não suportado" para "implementado" só com teste.

## T7 — FPU do EE e COP0 básico
Semântica não-IEEE do EE (arredondamento, denormais, sem NaN/Inf). **Aceite:** diferencial contra vetores documentados.

## T8 — VU0 macro mode
Modelo de VF/VI/ACC; instruções COP2 nomeadas (hoje `vu0_macro` genérico). **Aceite:** testes por instrução.

## T9 — Backend de GS (esboço) e adaptador por jogo
Implementar `Renderer` mínimo (Vulkan ou D3D11) consumindo pacotes GIF simples; documentar em `GameAdapter.manual_reimplementations()`.
**Aceite:** só alterar `implemented=True` quando houver teste visual/automatizado reproduzível.

## T10 — Formatos extras
CUE/BIN, UDF, CHD/CSO (somente leitura), ELF empacotado conhecido. **Aceite:** fixtures sintéticas.

## Fora de escopo (não fazer)
Embutir BIOS/jogos, "converter ISO para EXE" por renomeação/embrulho de emulador sem rotular como emulação.
