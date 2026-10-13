# PS2Native (protótipo experimental)

Ferramenta de **engenharia reversa e análise de portabilidade** de jogos de PlayStation 2 para Windows.

> ## ⚠️ O que isto É e o que NÃO é
> **É**: um analisador de ISO/ELF, um desmontador do R5900, um tradutor experimental de um
> *subconjunto* de instruções para C (com testes de semântica) e uma GUI para ver tudo isso.
>
> **NÃO é**: um conversor "ISO → EXE". **Nenhum jogo roda nativamente com esta ferramenta.**
> Não existem GS, VU, áudio, IOP nem kernel/BIOS implementados. Desmontar ≠ recuperar código-fonte.
> O status máximo hoje é "tradução parcial/total de código **sem runtime de hardware**".

## Instalação
```bash
python -m venv .venv
.venv\Scripts\activate          # Windows  (Linux/macOS: source .venv/bin/activate)
pip install -r requirements.txt  # só a GUI precisa do PySide6
```

## Uso
```bash
python -m ps2native make-demo-iso demo.iso        # ISO de demonstração PRÓPRIA (não comercial)
python -m ps2native analyze demo.iso -o out/ --package
python -m ps2native analyze-elf jogo.elf -o out/
python -m ps2native gui                           # interface gráfica (PySide6)
```
A GUI tem: seleção de ISO, análise automática, progresso, lista de executáveis, funções, instruções não
suportadas, compatibilidade estimada de **tradução**, status da portabilidade, exportação (.md/.json) e
geração do pacote **somente quando há funções traduzidas** (e rotulado como protótipo, nunca "nativo").

## Testes
```bash
python -m unittest discover -s tests -t . -v
```
Cobrem: decodificador, ELF, ISO9660 (2048 e 2352), análise, pacote, CLI e **semântica da tradução**
(C compilado × executor de referência em Python). Os testes de semântica precisam de `gcc`/`clang`
no PATH (são pulados sem ele). Usam apenas dados gerados por `ps2native/testgen.py` (sem material comercial).

## Gerar o .exe do aplicativo (Windows)
```powershell
powershell -ExecutionPolicy Bypass -File build_exe.ps1
```
Resultado: `dist\PS2Native\PS2Native.exe`. O workflow `.github/workflows/ci.yml` roda testes (Linux/Windows) e
gera o executável como artefato.

## Estrutura
Veja `docs/ARQUITETURA.md` (arquitetura, níveis de status) e `docs/PESQUISA.md` (pesquisa técnica e licenças).

## Limitações conhecidas
* Traduz só: ALU de 32 bits, shifts, `mult/multu`, HI/LO, loads/stores (`lb/lh/lw/ld`, `sb/sh/sw/sd`),
  `beq/bne/blez/bgtz/bltz/bgez`, `j`, `jal`, `jr $ra`. O resto fica registrado como **não suportado**.
* Sem GPRs de 128 bits → `lq/sq`, MMI e VU0/COP2 **não** são traduzidos (apenas detectados/contados).
* Sem `div/divu`, `add/sub` com trap, `lwl/lwr`, branch-likely, FPU, COP0, `syscall`, saltos indiretos.
* Limites de função são heurísticos; a varredura de segmentos executáveis pode contar dados como código.
* Nomes das tabelas MMI foram escritos de memória a partir do manual do EE: **revise** antes de confiar.
* Premissa: `jr $ra` retorna; `jal` vira chamada C direta. Sem exceções/TLB/cache/alinhamento.
* ISO: só ISO9660 (sem UDF puro, Joliet, multi-extent, CUE/BIN multi-trilha, CHD/CSO).
* Executáveis empacotados/criptografados não são reconhecidos como ELF.
* Mapa de hardware por `lui` é heurístico (pode ter falsos positivos/negativos).

## Licença e legalidade
Escolha a licença do seu repositório. Atenção: **PS2Recomp** é GPL-3.0 (verifique); não copie código dele
para um projeto com licença incompatível. Não distribua jogos, BIOS ou assets. Não sou advogado.
