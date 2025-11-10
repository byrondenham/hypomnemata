from __future__ import annotations
from dataclasses import dataclass, field
from typing import Protocol, Iterable, Iterator, runtime_checkable, Sequence

NoteId = str


@dataclass(frozen=True)
class Anchor:
    kind: str  # "block" or "heading"
    value: str  # "^label" name or slug


@dataclass(frozen=True)
class BlockLabel:
    name: str  # e.g. "riemann" for "^riemann"


@dataclass(frozen=True)
class Range:
    start: int  # byte/char offsets in the raw text (pick one and be consistent)
    end: int


@dataclass
class Block:
    kind: str  # "paragraph" | "heading" | "fence" | "list" | "media" | "other"
    range: Range
    label: BlockLabel | None = None
    heading_text: str | None = None
    fence_info: str | None = None


@dataclass(frozen=True)
class LinkTarget:
    id: NoteId
    anchor: Anchor | None = None
    rel: str | None = None  # purely descriptive; no semantic behaviour
    title_text: str | None = None  # "[[id|Title]]" helper
    range: Range | None = None


@dataclass(frozen=True)
class Link:
    source: NoteId
    target: LinkTarget
    range: Range | None = None


@dataclass
class Transclusion:
    target: LinkTarget  # ![[id]] or ![[id#^label]]
    range: Range | None = None


@dataclass
class NoteBody:
    raw: str
    blocks: list[Block] = field(default_factory=list)
    links: list[Link] = field(default_factory=list)
    transclusions: list[Transclusion] = field(default_factory=list)


@dataclass
class Note:
    id: NoteId
    meta: "MetaBag"
    body: NoteBody
