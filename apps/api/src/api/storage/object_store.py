"""``ObjectStore`` local (spec R3 §8.1/§14): acceso controlado bajo ``DATA_DIR``.

Sin S3/MinIO en el MVP. Rechaza path traversal, rutas absolutas y enlaces simbólicos que escapen
de la raíz. Las rutas internas nunca se incluyen en mensajes públicos.
"""

from __future__ import annotations

import os
import re
import shutil
import tempfile
from pathlib import Path
from typing import BinaryIO, Protocol

from api.reproducibility.hashing import sha256_file

_SEGMENT_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._+=-]{0,127}$")


class StoragePathError(ValueError):
    """Ruta fuera de la raíz permitida o con segmentos no válidos."""


class StorageObjectExists(FileExistsError):
    """Se intentó sobrescribir un objeto existente (los resultados no se sobrescriben)."""


class ObjectStore(Protocol):
    def resolve(self, relative: str) -> Path: ...
    def exists(self, relative: str) -> bool: ...
    def size(self, relative: str) -> int: ...
    def sha256(self, relative: str) -> str: ...
    def open_read(self, relative: str) -> BinaryIO: ...
    def write_bytes(self, relative: str, data: bytes, *, overwrite: bool = False) -> str: ...
    def delete(self, relative: str) -> bool: ...
    def delete_tree(self, relative: str) -> bool: ...


class LocalObjectStore:
    def __init__(self, root: Path) -> None:
        self.root = Path(root).resolve()
        self.root.mkdir(parents=True, exist_ok=True)

    def resolve(self, relative: str) -> Path:
        if not relative or relative.startswith(("/", "\\")) or "\x00" in relative:
            raise StoragePathError("Ruta no permitida")
        parts = relative.replace("\\", "/").split("/")
        if any(p in {"", ".", ".."} or not _SEGMENT_RE.match(p) for p in parts):
            raise StoragePathError("Ruta no permitida")
        candidate = self.root.joinpath(*parts)
        # resolve() sigue symlinks existentes: el destino final debe seguir bajo la raíz.
        resolved = candidate.resolve()
        if not resolved.is_relative_to(self.root):
            raise StoragePathError("Ruta fuera de la raíz de datos")
        return resolved

    def exists(self, relative: str) -> bool:
        return self.resolve(relative).is_file()

    def size(self, relative: str) -> int:
        return self.resolve(relative).stat().st_size

    def sha256(self, relative: str) -> str:
        return sha256_file(self.resolve(relative))

    def open_read(self, relative: str) -> BinaryIO:
        return self.resolve(relative).open("rb")

    def write_bytes(self, relative: str, data: bytes, *, overwrite: bool = False) -> str:
        """Escritura atómica (archivo temporal + rename). Devuelve el SHA-256 escrito."""
        target = self.resolve(relative)
        if target.exists() and not overwrite:
            raise StorageObjectExists("El objeto ya existe y no se sobrescribe")
        target.parent.mkdir(parents=True, exist_ok=True)
        fd, tmp = tempfile.mkstemp(dir=target.parent, prefix=".tmp-")
        try:
            with os.fdopen(fd, "wb") as fh:
                fh.write(data)
            Path(tmp).replace(target)
        except BaseException:
            Path(tmp).unlink(missing_ok=True)
            raise
        return sha256_file(target)

    def delete(self, relative: str) -> bool:
        target = self.resolve(relative)
        if target.is_file():
            target.unlink()
            return True
        return False

    def delete_tree(self, relative: str) -> bool:
        target = self.resolve(relative)
        if target.is_dir():
            shutil.rmtree(target)
            return True
        return False
