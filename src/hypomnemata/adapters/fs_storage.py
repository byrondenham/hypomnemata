from collections.abc import Iterable
from pathlib import Path

from ..core.ports import StorageStrategy


class FsStorage(StorageStrategy):
    def __init__(self, root: Path):
        self.root = root

    def _path(self, id: str) -> Path:
        return self.root / f"{id}.md"

    def read_raw(self, id: str) -> str | None:
        p = self._path(id)
        return p.read_text(encoding="utf-8") if p.exists() else None

    def write_raw(self, id: str, contents: str) -> None:
        self.root.mkdir(parents=True, exist_ok=True)
        self._path(id).write_text(contents, encoding="utf-8")

    def delete_raw(self, id: str) -> None:
        p = self._path(id)
        if p.exists():
            p.unlink()

    def list_all_ids(self) -> list[str]:
        if not self.root.exists():
            return []
        return [p.stem for p in self.root.glob("*.md")]
