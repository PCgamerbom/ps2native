"""Identificação heurística de formatos por assinatura binária e extensão."""
from __future__ import annotations

from typing import Optional

_MAGICS = [
    (b"\x7fELF", 0, "ELF (executável/módulo)"),
    (b"PS-X EXE", 0, "PS-X EXE (executável de PlayStation 1)"),
    (b"VAGp", 0, "VAG (áudio ADPCM do PlayStation)"),
    (b"TIM2", 0, "TIM2 (textura/imagem do PS2)"),
    (b"AFS\x00", 0, "AFS (arquivo de recursos CRI)"),
    (b"HCA\x00", 0, "HCA (áudio CRI)"),
    (b"RNC\x01", 0, "RNC (dados comprimidos, método 1)"),
    (b"RNC\x02", 0, "RNC (dados comprimidos, método 2)"),
    (b"CRILAYLA", 0, "CRILAYLA (dados comprimidos CRI)"),
    (b"MThd", 0, "MIDI"),
    (b"RIFF", 0, "RIFF (WAV/AVI/outros)"),
    (b"BIKi", 0, "Bink Video"),
    (b"\x00\x00\x01\xba", 0, "MPEG Program Stream (PSS/vídeo)"),
    (b"PK\x03\x04", 0, "ZIP"),
    (b"\x1f\x8b", 0, "gzip"),
    (b"Sony Computer Entertainment", 0, "Cabeçalho de dados Sony"),
]

_EXTENSIONS = [
    (".ADX", "ADX (provável, inferido pela extensão)"),
    (".AFS", "AFS (provável, inferido pela extensão)"),
    (".HCA", "HCA (provável, inferido pela extensão)"),
    (".PSS", "PSS (provável, inferido pela extensão)"),
    (".RNC", "RNC (provável, inferido pela extensão)"),
    (".TIM2", "TIM2 (provável, inferido pela extensão)"),
    (".TM2", "TIM2 (provável, inferido pela extensão)"),
    (".VAG", "VAG (provável, inferido pela extensão)"),
]


def identify(head: bytes, name: str = "") -> Optional[str]:
    if head.startswith(b"RIFF") and len(head) >= 12:
        subtype = head[8:12]
        if subtype == b"WAVE":
            return "WAVE (áudio RIFF)"
        if subtype == b"AVI ":
            return "AVI (vídeo RIFF)"
        if subtype == b"WEBP":
            return "WebP (imagem RIFF)"
    for magic, off, label in _MAGICS:
        if head[off:off + len(magic)] == magic:
            if label.startswith("ELF") and len(head) >= 18:
                et = int.from_bytes(head[16:18], "little")
                if et == 0xFF80:
                    return "IRX (módulo IOP, ELF e_type 0xFF80)"
            return label
    up = name.upper()
    if up.rsplit("/", 1)[-1] == "SYSTEM.CNF":
        return "SYSTEM.CNF (configuração de boot, inferido pelo nome)"
    if up.endswith(".IRX"):
        return "IRX (por extensão)"
    for extension, label in _EXTENSIONS:
        if up.endswith(extension):
            return label
    return None
