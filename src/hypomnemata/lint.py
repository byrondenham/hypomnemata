from dataclasses import dataclass
from typing import Protocol
from .core.model import Note, Range
from .core.ports import LinkResolver, Index


@dataclass
class Finding:
    severity: str  # "info" | "warn" | "error"
    message: str
    range: Range | None = None


class LintRule(Protocol):
    id: str

    def check(self, note: Note, resolver: LinkResolver, index: Index) -> list[Finding]:
        pass


class DeadLinksRule:
    id = "dead-links"

    def check(self, note: Note, resolver: LinkResolver, index: Index) -> list[Finding]:
        out: list[Finding] = []
        for link in note.body.links:
            if not resolver.exists(link.target):
                out.append(
                    Finding("error", f"Unknown note id {link.target.id}", link.range)
                )
            elif not resolver.anchor_ok(link.target):
                out.append(
                    Finding("warn", f"Unknown anchor for {link.target.id}", link.range)
                )
        return out
