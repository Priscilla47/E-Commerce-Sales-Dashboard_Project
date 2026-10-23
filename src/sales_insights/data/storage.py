"""Where order files come from.

Code that needs a file talks to the small ``Storage`` interface instead of the file system,
so another place (a cloud bucket, for example) can be plugged in without touching it.
"""

from __future__ import annotations

from pathlib import Path
from typing import Protocol, runtime_checkable


class StorageError(ValueError):
    """The requested name is not allowed in this storage."""


@runtime_checkable
class Storage(Protocol):
    """A flat collection of named files."""

    def read(self, name: str) -> bytes:
        """Return the content of a file. Raise FileNotFoundError if it does not exist."""
        ...

    def exists(self, name: str) -> bool:
        """Tell whether a file with this name exists."""
        ...

    def list(self) -> list[str]:
        """Return the names of all files, sorted."""
        ...


class LocalStorage:
    """Files in a directory of the local file system.

    Names are relative to the root directory. A name that would leave the root (``..``, an
    absolute path, a symbolic link pointing outside) raises StorageError.
    """

    def __init__(self, root: str | Path) -> None:
        self.root = Path(root).resolve()

    def read(self, name: str) -> bytes:
        path = self._resolve(name)
        if not path.is_file():
            raise FileNotFoundError(f"File not found in storage: {name}")
        return path.read_bytes()

    def exists(self, name: str) -> bool:
        return self._resolve(name).is_file()

    def list(self) -> list[str]:
        """Names of the files directly inside the root; sub-directories are not listed."""
        return sorted(path.name for path in self.root.iterdir() if path.is_file())

    def _resolve(self, name: str) -> Path:
        try:
            path = (self.root / name).resolve()
        except ValueError as error:  # for instance a null byte in the name
            raise StorageError(f"Invalid name: {name!r}") from error
        if path == self.root or not path.is_relative_to(self.root):
            raise StorageError(f"Name is outside the storage: {name!r}")
        return path
