import re, io
import yaml
from typing import Any
from ..core.ports import FrontmatterCodec, NoteCodec
from ..core.model import Note

_FM = re.compile(r"^\s*---\s*\n(.*?)\n---\s*\n?", re.DOTALL)


class YamlFrontmatter(FrontmatterCodec):
    def decode(self, text: str) -> tuple[dict[str, Any], str]:
        m = _FM.match(text)
        if not m:
            return {}, text
        fm = yaml.safe_load(io.StringIO(m.group(1))) or {}
        body = text[m.end() :]
        return (fm, body)

    def encode(self, meta: dict[str, Any]) -> str:
        if not meta:
            return ""
        buf = io.StringIO()
        yaml.safe_dump(meta, buf, sort_keys=False, allow_unicode=True)
        return f"---\n{buf.getvalue()}---\n"


class MarkdownNoteCodec(NoteCodec):
    def __init__(self, fm: YamlFrontmatter):
        self.fm = fm

    def decode_file(self, text: str, id: str):
        meta, body = self.fm.decode(text)
        return meta, body

    def encode_file(self, note: Note) -> str:
        # IMPORTANT: core never *requires* schema; we simply mirror whatever is in MetaBag
        meta = dict(note.meta)
        # Non-binding: mirror id if user stored one; filename remains source of truth
        if "id" not in meta:
            meta["id"] = note.id
        return self.fm.encode(meta) + note.body.raw
