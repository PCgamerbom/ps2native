"""Interfaces modulares para as partes de hardware (FASE 5) e adaptadores por jogo (FASE 6).

IMPORTANTE: nenhuma destas interfaces tem implementação real ainda. As classes `Null*`
existem apenas para o sistema poder PERGUNTAR se o backend está implementado
(`implemented = False`) e, com isso, nunca declarar um port como nativo/completo.
"""
from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Dict, List, Type


class Backend(ABC):
    implemented: bool = False
    name: str = "abstract"


class Renderer(Backend):
    """Direct3D 11/12 ou Vulkan. Deve consumir pacotes GIF/GS (PATH1/2/3) e emular o GS."""
    @abstractmethod
    def submit_gif_packet(self, data: bytes) -> None: ...
    @abstractmethod
    def present(self) -> None: ...


class AudioBackend(Backend):
    """Saída de áudio no Windows (WASAPI/XAudio2) alimentada pelo SPU2 (reimplementado)."""
    @abstractmethod
    def submit_pcm(self, samples: bytes, rate: int) -> None: ...


class InputBackend(Backend):
    """Controles (XInput/RawInput) mapeados para o protocolo do DualShock 2 (via SIO2/PAD)."""
    @abstractmethod
    def poll(self) -> Dict[str, float]: ...


class TimingBackend(Backend):
    """Temporização/sincronização: timers do EE, VBlank/HBlank, sincronização com o GS."""
    @abstractmethod
    def wait_vblank(self) -> None: ...


class MemoryManager(Backend):
    """Mapa de memória do EE (32 MB, scratchpad, I/O mapeado, TLB/KSEG)."""
    @abstractmethod
    def read(self, addr: int, size: int) -> bytes: ...
    @abstractmethod
    def write(self, addr: int, data: bytes) -> None: ...


class VectorUnit(Backend):
    """VU0 (macro/micro) e VU1 (micro-programas via VIF1/XGKICK)."""
    @abstractmethod
    def exec_vu0_macro(self, word: int) -> None: ...
    @abstractmethod
    def run_vu1_microprogram(self, addr: int) -> None: ...


def _null(base: Type[Backend], label: str) -> Type[Backend]:
    ns = {"implemented": False, "name": f"Null{label}"}
    for m in getattr(base, "__abstractmethods__", ()):
        ns[m] = lambda self, *a, _m=m, **k: (_ for _ in ()).throw(
            NotImplementedError(f"{label}.{_m} não implementado"))
    return type(f"Null{label}", (base,), ns)


NullRenderer = _null(Renderer, "Renderer")
NullAudio = _null(AudioBackend, "Audio")
NullInput = _null(InputBackend, "Input")
NullTiming = _null(TimingBackend, "Timing")
NullMemory = _null(MemoryManager, "Memory")
NullVectorUnit = _null(VectorUnit, "VectorUnit")

REQUIRED = ["renderer", "audio", "input", "timing", "memory", "vector_unit"]


def default_backends() -> Dict[str, Backend]:
    return {"renderer": NullRenderer(), "audio": NullAudio(), "input": NullInput(),
            "timing": NullTiming(), "memory": NullMemory(), "vector_unit": NullVectorUnit()}


def adapters_ready(backends: Dict[str, Backend]) -> bool:
    return all(k in backends and backends[k].implemented for k in REQUIRED)


class GameAdapter(ABC):
    """Adaptador específico de um jogo: documenta o que precisa de reimplementação manual."""
    title_id: str = ""
    title: str = ""

    @abstractmethod
    def manual_reimplementations(self) -> List[str]:
        """Funções/sistemas que exigem reconstrução manual (documentação obrigatória)."""

    def hooks(self) -> Dict[int, str]:
        """Mapa endereço -> nome da função nativa que substitui o código original."""
        return {}


_ADAPTERS: Dict[str, GameAdapter] = {}


def register_adapter(a: GameAdapter) -> None:
    if not a.title_id:
        raise ValueError("adaptador sem title_id")
    _ADAPTERS[a.title_id.upper()] = a


def get_adapter(title_id: str):
    return _ADAPTERS.get(title_id.upper())


class DemoAdapter(GameAdapter):
    """Adaptador do executável de demonstração criado em testgen.py (não é um jogo comercial)."""
    title_id = "DEMO_000.00"
    title = "PS2Native demo"

    def manual_reimplementations(self) -> List[str]:
        return ["GS: leitura de 0x12000000 (registradores privilegiados) — reimplementar no Renderer",
                "syscall #0x3c: kernel do PS2 — reimplementar no runtime de BIOS"]


register_adapter(DemoAdapter())
