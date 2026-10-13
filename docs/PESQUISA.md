# FASE 1 — Pesquisa técnica (resumo)

> Escopo honesto: pesquisa feita a partir de fontes públicas (READMEs/wikis dos projetos e
> documentação do hardware). Nada aqui foi validado executando jogos. Itens marcados com
> **[verificar]** devem ser conferidos nas fontes originais antes de qualquer decisão.

## Projetos públicos relevantes
| Projeto | O que faz | Licença | Uso no PS2Native |
|---|---|---|---|
| **PS2Recomp** (ran-j) | Recompilador estático ELF PS2 → C++ + runtime; módulos de análise, recompilação e runtime; suporta MMI e VU0 em modo macro; ainda experimental, sem jogos jogáveis na época da pesquisa | GPL-3.0 (segundo notícias) **[verificar no repositório]** | Referência de arquitetura. **Não copiamos código** (GPL-3.0 contaminaria este projeto) |
| **PCSX2** | Emulador de PS2 (interpretador + JIT) | GPL-3.0 **[verificar]** | Referência de semântica do hardware; solução *baseada em emulação* |
| **Ghidra** (NSA) | Descompilador/desmontador; há suporte a MIPS e plug-ins comunitários para o EE (R5900) **[verificar]** | Apache-2.0 | Integração futura (exportar funções/símbolos) |
| **LLVM** | Infra de compilação; MIPS é suportado, R5900 não é um alvo oficial | Apache-2.0 com exceções LLVM | Candidato a back-end de IR no futuro |
| **N64Recomp / XenonRecomp** | Recompilação estática de N64/Xbox 360 para C++ | ver repositórios **[verificar]** | Mostram que o modelo "recompilar + runtime específico por jogo" funciona |

## Decisão: LLVM, tradutor existente ou sistema próprio?
* **Protótipo atual: IR próprio minúsculo + emissão de C.** Motivo: dá para verificar a semântica
  por teste diferencial (C compilado com gcc × executor Python) sem dependências pesadas.
* **LLVM**: melhor para otimização e para gerar código direto, mas o R5900 tem GPRs de 128 bits
  e MMI/VU0, que exigem tipos/intrínsecos próprios. Recomendado quando o modelo de estado estiver estável.
* **Tradutor existente (ex.: PS2Recomp)**: aproveitar é viável **apenas** respeitando a GPL-3.0
  (projeto derivado também GPL-3.0) ou usando-o como ferramenta externa (invocação por linha de comando).

## Arquitetura do PS2 (o que importa para portar)
* **Emotion Engine (EE)**: CPU R5900 (MIPS III/IV + extensões), GPRs de 128 bits, FPU não-IEEE,
  instruções MMI (SIMD inteiro), HI/LO e HI1/LO1, registrador SA.
* **VU0/VU1**: unidades vetoriais. VU0 acessível em *macro mode* (COP2) pelo EE; VU1 roda micro-programas
  (VIF1/XGKICK). Jogos costumam trazer micro-programas próprios → **reimplementação por jogo**.
* **GS (Graphics Synthesizer)**: recebe pacotes GIF via DMA; semântica de rasterização específica
  (blending, mapas de tela, eDRAM de 4 MB). Não traduzível "automaticamente".
* **IOP (R3000 + PS1)**: roda módulos IRX (disco, pad, memcard, SPU2). Outro conjunto de instruções.
* **SPU2**: áudio ADPCM por hardware, DMA próprio.
* **Kernel/BIOS**: syscalls (threads, semáforos, DMA, etc.) precisam de runtime.

## O que dá para automatizar × o que exige trabalho por jogo
| Automatizável | Específico por jogo |
|---|---|
| Ler ISO9660, SYSTEM.CNF, ELF, símbolos | Micro-programas de VU1 |
| Desmontar/identificar instruções | Uso de GS (efeitos, ordem de pacotes, sincronização) |
| Traduzir ALU/memória/branches com semântica verificada | Overlays, auto-modificação, código empacotado/criptografado |
| Detectar referências a hardware e syscalls | Chamadas indiretas / tabelas de saltos |
| Gerar relatórios | Áudio (SPU2/streams), FMV (PSS/IPU), IRX/IOP |

## Legal
Analisar uma ISO que você possui para fins de interoperabilidade é uma coisa; distribuir o jogo,
assets ou binários traduzidos é outra. Este projeto **não copia assets** nem BIOS. Consulte um advogado
para o seu caso — não sou advogado.
