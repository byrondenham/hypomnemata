from typing import Protocol, AsyncIterable, Iterable, Any
from .model import NoteId, Note, NoteBody, LinkTarget, Block


class StorageStrategy(Protocol):
    """
    Flat store: one directory, files named <id>.md
    """

    def read_raw(self, id: NoteId) -> str | None:
        pass

    def write_raw(self, id: NoteId, contents: str) -> None:
        pass

    def delete_raw(self, id: NoteId) -> None:
        pass

    def list_all_ids(self) -> Iterable[NoteId]:
        pass


class ParserStrategy(Protocol):
    """
    Parse Markdown into blocks/links/transclusions; optionally lift some metadata
    but MUST NOT require any schema.
    """

    def parse(self, text: str, id: NoteId) -> NoteBody:
        pass


class FrontmatterCodec(Protocol):
    """
    Round-trip optional frontmatter without enforcing schema.
    """

    def decode(self, text: str) -> dict[str, Any] | tuple[dict[str, Any], str]:
        pass

    def encode(self, meta: dict[str, Any]) -> str:
        pass


class NoteCodec(Protocol):
    """
    Compose FrontmatterCode with raw body.
    """

    def decode_file(self, text: str, id: NoteId) -> tuple[dict[str, Any], str]:
        pass

    def encode_file(self, note: Note) -> str:
        pass


class IdGenerator(Protocol):
    def new_id(self) -> NoteId:
        pass


class LinkResolver(Protocol):
    """
    ID-only resolution (anchors optional). Titles/aliases are UI sugar only.
    """

    def exists(self, target: LinkTarget) -> bool:
        pass

    def anchor_ok(self, target: LinkTarget) -> bool:
        pass


class Index(Protocol):
    """
    Cache derived state; safe to rebuild at any time.
    """

    def rebuild(self) -> None:
        pass

    def links_out(self, id: NoteId) -> list:
        pass

    def links_in(self, id: NoteId) -> list:
        pass

    def blocks(self, id: NoteId) -> list[Block]:
        pass

    def search(self, query: str) -> list[NoteId]:
        pass


class ExportAdapter(Protocol):
    def export_all(self, out_dir: str) -> None:
        pass


class Renderer(Protocol):
    def render_html(self, note: Note) -> str:
        pass
