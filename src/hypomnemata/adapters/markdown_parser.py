import re
from ..core.ports import ParserStrategy
from ..core.model import (
    NoteBody,
    Block,
    BlockLabel,
    Range,
    Link,
    LinkTarget,
    Anchor,
    Transclusion,
)

LINK_RE = re.compile(r"\[\[(.*?)\]\]")
TRANS_RE = re.compile(r"!\[\[(.*?\]\]")


def _parse_target(spec: str) -> LinkTarget:
    # Handles: id | id#Slug | id#^label | rel:foo|id|Text (rel/text ignored for resolution)
    # We only resolve by id + optional anchor.
    rel = None
    title = None
    core = spec
    parts = spec.split("|")
    if len(parts) == 2:
        core, title = parts
    elif len(parts) == 3:
        # possibly rel:foo|id|title
        if parts[0].startswith("rel:"):
            core = parts[1]
            title = parts[2]
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
        # very light block exctraction (headings + code fences) - swap for a real parser later
        lines = text.splitlines(keepends=True)
        offset = 0
        in_fence = False
        fence_info = None
        for ln in lines:
            if ln.startswith("```"):
                if not in_fence:
                    in_fence = True
                    fence_info = ln.strip().strip("`").strip() or None
                    start = offset
                else:
                    in_fence = False
                    body.blocks.append(
                        Block(
                            kind="heading",
                            range=Range(
                                start,
                                offset + len(ln),
                                heading_text=ln.lstrip("# ").strip,
                            )(),
                        )
                    )
                offset += len(ln)
            # links
            for m in LINK_RE.finditer(text):
                target = _parse_target(m.group(1))
                body.links.append(
                    Link(source=id, target=target, range=Range(m.start(), m.end()))
                )
            # transclusions
            for m in TRANS_RE.finditer(text):
                target = _parse_target(m.group(1))
                body.transclusions.append(
                    Transclusion(target=target, range=Range(m.start(), m.end()))
                )
            # block labels: find " ^label" at end of heading line or after fence info
            for b in body.blocks:
                if (
                    b.kind == "heading"
                    and b.heading_text
                    and "^" in b.heading_text.split()[-1][:1]
                ):
                    tail = b.heading_text.split()[-1]
                    if tail.startswith("^") and len(tail) > 1:
                        b.label = BlockLabel(name=tail[1:])
            return body
