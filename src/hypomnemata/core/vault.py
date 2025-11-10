from collections.abc import Iterable

from .meta import MetaBag
from .model import Note, NoteId
from .ports import NoteCodec, ParserStrategy, StorageStrategy


class Vault:
    def __init__(
        self, storage: StorageStrategy, parser: ParserStrategy, codec: NoteCodec
    ):
        self.storage = storage
        self.parser = parser
        self.codec = codec

    def get(self, id: NoteId) -> Note | None:
        raw = self.storage.read_raw(id)
        if raw is None:
            return None
        meta_partial, body_text = self.codec.decode_file(raw, id)
        meta = MetaBag(meta_partial)
        body = self.parser.parse(body_text, id)
        return Note(id=id, meta=meta, body=body)

    def put(self, note: Note) -> None:
        contents = self.codec.encode_file(note)
        self.storage.write_raw(note.id, contents)

    def delete(self, id: NoteId) -> None:
        # intentionally simple; storage implementation decides how to delete
        self.storage.write_raw(id, "")  # or a dedicated delete API

    def list_ids(self) -> Iterable[NoteId]:
        return self.storage.list_all_ids()
