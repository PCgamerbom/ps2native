"""Identificação de formatos conhecidos por magic bytes (heurística, não prova)."""
from __future__ import annotations

from typing import Optional

_MAGICS = [
    (b"\x7fELF", 0, "ELF (executável/módulo)"),
    (b"PS-X EXE", 0, "PS-X EXE (executável de PlayStation 1)"),
    (b"VAGp", 0, "VAG (áudio ADPCM do PlayStation)"),
    (b"TIM2", 0, "TIM2 (textura/imagem do PS2)"),
    (b"AFS\x00", 0, "AFS (arquivo de recursos CRI)"),
    (b"RIFF", 0, "RIFF (WAV/AVI/outros)"),
    (b"BIKi", 0, "Bink Video"),
    (b"\x00\x00\x01\xba", 0, "MPEG Program Stream (PSS/vídeo)"),
    (b"PK\x03\x04", 0, "ZIP"),
    (b"\x1f\x8b", 0, "gzip"),
    (b"Sony Computer Entertainment", 0, "Cabeçalho de dados Sony"),
]


def identify(head: bytes, name: str = "") -> Optional[str]:
    for magic, off, label in _MAGICS:
        if head[off:off + len(magic)] == magic:
            if label.startswith("ELF") and len(head) >= 18:
                et = int.from_bytes(head[16:18], "little")
                if et == 0xFF80:
                    return "IRX (módulo IOP, ELF e_type 0xFF80)"
            return label
    up = name.upper()
    if up.endswith(".IRX"):
        return "IRX (por extensão)"
    return None
