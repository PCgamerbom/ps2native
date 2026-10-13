# Arquitetura

```
ISO ──► iso9660.py ──► SYSTEM.CNF ──► ELF principal
                                         │
                      elf.py (segmentos, seções, símbolos)
                                         │
                      mips.py (decodificador R5900 + flags PS2)
                                         │
              analysis.py (funções, hardware, syscalls, estatísticas)
                                         │
        translator.py ◄── ir.py (lift → IR → interpretador Python / emissão C)
                                         │
              package.py (pacote de análise)  report.py (JSON/MD)
                                         │
                    cli.py / gui.py (PySide6)
interfaces.py: Renderer/Audio/Input/Timing/Memory/VectorUnit + GameAdapter (sem implementação real)
```

## Módulos
* `iso9660.py` — leitor de ISO9660 (2048/2352/2336), SYSTEM.CNF, caminhos. Nunca executa conteúdo.
* `elf.py` — ELF32 LE (EE e IRX). Verifica truncamento.
* `mips.py` — decodificador. Marca `ps2_specific`, `known`, `kind` (branch/jump/call/return/…).
* `ir.py` — IR de expressões 64-bit. `lift()` levanta instruções suportadas; qualquer outra levanta
  `Unsupported(motivo)`. O MESMO IR é interpretado em Python e emitido em C.
* `translator.py` — descobre limites da função, trata delay slots/branches/jal/jr ra, gera C. Instrução não
  suportada vira `ps2_unsupported()` (aborta) e entra no relatório.
* `analysis.py` — pipeline completo + `port_status()`.
* `package.py` — gera `ps2rt.h`, `functions.c`, relatórios, `STATUS.txt`.
* `interfaces.py` — contratos para GS/áudio/controle/tempo/memória/VU e adaptadores por jogo.

## Níveis de status (FASE 7)
| Nível | Significado |
|---|---|
| 0 | Apenas analisado |
| 1 | Tradução parcial (há funções com instruções não suportadas) |
| 2 | Todo o código descoberto traduzido, mas **sem runtime de hardware** |
| 3 | Candidato a port nativo: tudo traduzido, sem hardware pendente **e** todos os backends `implemented=True` |

No protótipo, `Null*` backends têm `implemented=False`: o nível 3 é inalcançável de propósito.
Se um dia a execução depender de emular CPU/hardware do PS2, o resultado deve ser classificado como
**solução baseada em emulação**, nunca como nativa.

## Como testamos a semântica
`tests/test_translation.py` gera C a partir de programas MIPS escritos à mão, compila com gcc/clang
e compara registradores (e memória via loads) com um executor de referência em Python, em ~150 entradas
(inclui bordas: 0x7FFFFFFF, 0x80000000, valores de 64 bits aleatórios). Se não houver compilador C, esses
testes são pulados (e isso é dito no resultado).

## Para estender (próximos passos realistas)
1. VU0 macro e MMI exigem GPRs de 128 bits no estado (`uint64_t r[32][2]`) + testes diferenciais.
2. `div/divu`, `add/sub` com trap, `lwl/lwr`, branch-likely, 64-bit (`dadd*`, `ld/sd` já ok).
3. FPU do EE (arredondamento/denormais próprios).
4. Descoberta de funções mais robusta (jump tables, símbolos de Ghidra).
5. Runtime de syscalls/BIOS e um backend de GS (Vulkan/D3D). Esta é a parte gigante.
