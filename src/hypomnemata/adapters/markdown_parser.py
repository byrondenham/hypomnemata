import re

from ..core.model import (
    Anchor,
    Block,
    BlockLabel,
    Link,
    LinkTarget,
    NoteBody,
    Range,
    Transclusion,
)
from ..core.ports import ParserStrategy

LINK_RE = re.compile(r"\[\[(.*?)\]\]")
TRANS_RE = re.compile(r"!\[\[(.*?)\]\]")


def _parse_target(spec: str) -> LinkTarget:
    # Handles: id | id#Slug | id#^label | rel:foo|id|Text (rel/text ignored for resolution)
    # We only resolve by id + optional anchor.
    core = spec
    parts = spec.split("|")
    if len(parts) == 2:
        core, _title = parts
    elif len(parts) == 3:
        # possibly rel:foo|id|title
        if parts[0].startswith("rel:"):
            core = parts[1]
    if "#^" in core:
        id_, label = core.split("#^", 1)
        return LinkTarget(
            id=id_.strip(), anchor=Anchor(kind="block", value=label.strip())
        )
    elif "#" in core:
        id_, slug = core.split("#", 1)
        return LinkTarget(
            id=id_.strip(), anchor=Anchor(kind="heading", value=slug.strip())
        )
    else:
        return LinkTarget(id=core.strip())


class MarkdownParser(ParserStrategy):
    def parse(self, text: str, id: str) -> NoteBody:
        body = NoteBody(raw=text)
        
        # Parse headings (simple implementation)
        lines = text.splitlines(keepends=True)
        offset = 0
        for ln in lines:
            if ln.startswith("#"):
                heading_text = ln.lstrip("# ").strip()
                body.blocks.append(
                    Block(
                        kind="heading",
                        range=Range(offset, offset + len(ln)),
                        heading_text=heading_text,
                    )
                )
            offset += len(ln)
        
        # Parse links
        for m in LINK_RE.finditer(text):
            target = _parse_target(m.group(1))
            body.links.append(
                Link(source=id, target=target, range=Range(m.start(), m.end()))
            )
        
        # Parse transclusions
        for m in TRANS_RE.finditer(text):
            target = _parse_target(m.group(1))
            body.transclusions.append(
                Transclusion(target=target, range=Range(m.start(), m.end()))
            )
        
        # Extract block labels from headings
        for b in body.blocks:
            if b.kind == "heading" and b.heading_text:
                words = b.heading_text.split()
                if words and words[-1].startswith("^") and len(words[-1]) > 1:
                    b.label = BlockLabel(name=words[-1][1:])
        
        return body
