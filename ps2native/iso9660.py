"""Leitor somente-leitura de imagens ISO9660 (formato usado por discos de PS2).

Nunca executa nada do conteúdo da imagem. Suporta setores 2048 (ISO "cooked") e
layouts brutos 2352 (Mode1/Mode2 Form1) e 2336. NÃO suporta: UDF puro, Joliet,
Rock Ridge, arquivos multi-extent, formatos CUE/BIN com várias trilhas, CSO/CHD.
"""
from __future__ import annotations

import io
import re
import struct
from dataclasses import dataclass, field
from typing import BinaryIO, Dict, List, Optional, Union

# (tamanho do setor, offset dos dados do usuário dentro do setor)
LAYOUTS = [(2048, 0), (2352, 16), (2352, 24), (2336, 8)]
SECTOR_DATA = 2048


class IsoError(Exception):
    pass


@dataclass
class IsoEntry:
    path: str  # caminho normalizado, ex.: "/DATA/TEST.VAG"
    lba: int
    size: int
    is_dir: bool

    @property
    def name(self) -> str:
        return self.path.rsplit("/", 1)[-1]


@dataclass
class SystemCnf:
    raw: str
    values: Dict[str, str] = field(default_factory=dict)

    @property
    def boot_key(self) -> Optional[str]:
        for k in ("BOOT2", "BOOT"):
            if k in self.values:
                return k
        return None

    @property
    def boot_path(self) -> Optional[str]:
        k = self.boot_key
        if not k:
            return None
        v = self.values[k].strip()
        v = re.sub(r"^[A-Za-z0-9]+:", "", v)  # remove "cdrom0:" / "cdrom:"
        v = v.replace("\\", "/").lstrip("/")
        v = re.sub(r";\d+$", "", v)
        return "/" + v

    @property
    def platform(self) -> str:
        return {"BOOT2": "PlayStation 2", "BOOT": "PlayStation 1"}.get(self.boot_key or "", "desconhecida")


def parse_system_cnf(text: str) -> SystemCnf:
    vals: Dict[str, str] = {}
    for line in text.replace("\r", "\n").split("\n"):
        if "=" in line:
            k, v = line.split("=", 1)
            vals[k.strip().upper()] = v.strip()
    return SystemCnf(raw=text, values=vals)


class IsoImage:
    def __init__(self, source: Union[str, BinaryIO]):
        self._own = isinstance(source, str)
        self._f: BinaryIO = open(source, "rb") if self._own else source  # type: ignore[arg-type]
        self._f.seek(0, io.SEEK_END)
        self.total_size = self._f.tell()
        self.sector_size, self.data_offset = self._detect_layout()
        pvd = self.read_sector(16)
        if pvd[0] != 1 or pvd[1:6] != b"CD001":
            raise IsoError("Volume descriptor primário ISO9660 inválido")
        self.system_id = pvd[8:40].decode("ascii", "replace").strip()
        self.volume_id = pvd[40:72].decode("ascii", "replace").strip()
        self.volume_blocks = struct.unpack_from("<I", pvd, 80)[0]
        block = struct.unpack_from("<H", pvd, 128)[0]
        if block != SECTOR_DATA:
            raise IsoError(f"Tamanho de bloco lógico não suportado: {block}")
        self._root = self._parse_record(pvd[156:190], "")

    def close(self) -> None:
        if self._own:
            self._f.close()

    def __enter__(self):
        return self

    def __exit__(self, *a):
        self.close()

    # -- baixo nível ---------------------------------------------------------
    def _detect_layout(self):
        for ss, off in LAYOUTS:
            pos = 16 * ss + off
            self._f.seek(pos)
            head = self._f.read(6)
            if len(head) == 6 and head[1:6] == b"CD001":
                return ss, off
        raise IsoError("Não foi possível detectar ISO9660 (setor 16 sem 'CD001')")

    def read_sector(self, lba: int) -> bytes:
        self._f.seek(lba * self.sector_size + self.data_offset)
        data = self._f.read(SECTOR_DATA)
        if len(data) != SECTOR_DATA:
            raise IsoError(f"Setor {lba} fora da imagem")
        return data

    def read_extent(self, lba: int, size: int, limit: Optional[int] = None) -> bytes:
        want = size if limit is None else min(size, limit)
        out = bytearray()
        sec = lba
        while len(out) < want:
            out += self.read_sector(sec)
            sec += 1
        return bytes(out[:want])

    # -- diretórios -----------------------------------------------------------
    @staticmethod
    def _parse_record(rec: bytes, parent: str) -> IsoEntry:
        lba = struct.unpack_from("<I", rec, 2)[0]
        size = struct.unpack_from("<I", rec, 10)[0]
        flags = rec[25]
        nlen = rec[32]
        raw = rec[33:33 + nlen]
        if raw in (b"\x00", b"\x01"):
            name = ""
        else:
            name = raw.decode("ascii", "replace")
            name = re.sub(r";\d+$", "", name)
        path = (parent + "/" + name) if name else (parent or "/")
        return IsoEntry(path or "/", lba, size, bool(flags & 2))

    def _list_dir(self, d: IsoEntry) -> List[IsoEntry]:
        data = self.read_extent(d.lba, d.size)
        out: List[IsoEntry] = []
        pos = 0
        while pos < len(data):
            ln = data[pos]
            if ln == 0:  # padding até o próximo setor
                pos = (pos // SECTOR_DATA + 1) * SECTOR_DATA
                continue
            rec = data[pos:pos + ln]
            pos += ln
            if len(rec) < 34:
                break
            if rec[32] == 1 and rec[33:34] in (b"\x00", b"\x01"):
                continue
            parent = "" if d.path == "/" else d.path
            out.append(self._parse_record(rec, parent))
        return out

    def walk(self, max_entries: int = 200000) -> List[IsoEntry]:
        result: List[IsoEntry] = []
        seen = set()
        stack = [self._root]
        while stack:
            d = stack.pop()
            if d.lba in seen:
                continue
            seen.add(d.lba)
            for e in self._list_dir(d):
                result.append(e)
                if e.is_dir:
                    stack.append(e)
                if len(result) >= max_entries:
                    raise IsoError("Limite de entradas excedido (imagem suspeita)")
        result.sort(key=lambda e: e.path.upper())
        return result

    def find(self, path: str, entries: Optional[List[IsoEntry]] = None) -> Optional[IsoEntry]:
        want = path.upper()
        for e in entries if entries is not None else self.walk():
            if e.path.upper() == want:
                return e
        return None

    def read_file(self, e: IsoEntry, limit: Optional[int] = None) -> bytes:
        return self.read_extent(e.lba, e.size, limit)
