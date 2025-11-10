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
from ..core.utils import slugify

LINK_RE = re.compile(r"\[\[(.*?)\]\]")
TRANS_RE = re.compile(r"!\[\[(.*?)\]\]")
HEADING_RE = re.compile(r"^(#{1,6})\s+(.+)$")
FENCE_START_RE = re.compile(r"^```(.*)$")


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
        
        # Parse blocks (headings, fences, etc.)
        lines = text.splitlines(keepends=True)
        offset = 0
        in_fence = False
        fence_start = 0
        fence_info = ""
        
        for _i, ln in enumerate(lines):
            line_stripped = ln.rstrip('\n\r')
            
            # Check for fence start/end
            if line_stripped.startswith("```"):
                if not in_fence:
                    # Starting a fence
                    in_fence = True
                    fence_start = offset
                    fence_match = FENCE_START_RE.match(line_stripped)
                    fence_info = fence_match.group(1).strip() if fence_match else ""
                else:
                    # Ending a fence
                    in_fence = False
                    fence_end = offset + len(ln)
                    
                    # Extract label from fence_info (e.g., "python ^label")
                    label = None
                    if "^" in fence_info:
                        parts = fence_info.split()
                        for part in parts:
                            if part.startswith("^") and len(part) > 1:
                                label = BlockLabel(name=part[1:])
                                break
                    
                    body.blocks.append(
                        Block(
                            kind="fence",
                            range=Range(fence_start, fence_end),
                            fence_info=fence_info,
                            label=label,
                        )
                    )
                    fence_info = ""
            
            # Check for heading (only if not in fence)
            elif not in_fence:
                heading_match = HEADING_RE.match(line_stripped)
                if heading_match:
                    hashes = heading_match.group(1)
                    heading_text = heading_match.group(2).strip()
                    level = len(hashes)
                    
                    # Check for label at end of heading
                    label = None
                    words = heading_text.split()
                    if words and words[-1].startswith("^") and len(words[-1]) > 1:
                        label = BlockLabel(name=words[-1][1:])
                        # Remove label from heading_text for slug generation
                        heading_text_for_slug = " ".join(words[:-1])
                    else:
                        heading_text_for_slug = heading_text
                    
                    slug = slugify(heading_text_for_slug) if heading_text_for_slug else ""
                    
                    body.blocks.append(
                        Block(
                            kind="heading",
                            range=Range(offset, offset + len(ln)),
                            heading_text=heading_text,
                            heading_level=level,
                            heading_slug=slug,
                            label=label,
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
        
        return body
