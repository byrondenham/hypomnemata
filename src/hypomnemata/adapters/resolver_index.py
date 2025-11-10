from collections import defaultdict

from ..core.model import Block, Link, LinkTarget, NoteId
from ..core.ports import Index, LinkResolver
from ..core.vault import Vault


class DefaultResolver(LinkResolver):
    def __init__(self, vault: Vault):
        self.vault = vault

    def exists(self, target: LinkTarget) -> bool:
        return self.vault.get(target.id) is not None

    def anchor_ok(self, target: LinkTarget) -> bool:
        if target.anchor is None:
            return True
        note = self.vault.get(target.id)
        if not note:
            return False
        labels = {b.label.name for b in note.body.blocks if b.label}
        slugs = {
            (b.heading_text or "").strip().lower().replace(" ", "-")
            for b in note.body.blocks
            if b.kind == "heading"
        }
        if target.anchor.kind == "block":
            return target.anchor.value in labels
        return target.anchor.value.lower() in slugs


class InMemoryIndex(Index):
    def __init__(self, vault: Vault):
        self.vault = vault
        self._links_out: dict[str, list[Link]] = defaultdict(list)
        self._links_in: dict[str, list[Link]] = defaultdict(list)
        self._blocks: dict[str, list[Block]] = defaultdict(list)

    def rebuild(self) -> None:
        self._links_out.clear()
        self._links_in.clear()
        self._blocks.clear()
        for nid in self.vault.list_ids():
            note = self.vault.get(nid)
            if not note:
                continue
            self._links_out[nid] = note.body.links
            for link in note.body.links:
                self._links_in[link.target.id].append(link)
            self._blocks[nid] = note.body.blocks

    def links_out(self, id: str) -> list[Link]:
        return self._links_out[id]

    def links_in(self, id: str) -> list[Link]:
        return self._links_in[id]

    def blocks(self, id: str) -> list[Block]:
        return self._blocks[id]

    def search(self, query: str) -> list[NoteId]:
        q = query.lower()
        hits = []
        for nid in self.vault.list_ids():
            n = self.vault.get(nid)
            if not n:
                continue
            if q in n.body.raw.lower():
                hits.append(nid)
        return hits
