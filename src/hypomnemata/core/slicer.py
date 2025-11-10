"""Slicing engine for extracting portions of notes based on anchors."""

from .model import Anchor, Block, Note


def find_label(note: Note, label: str) -> Block | None:
    """Find a block with the given label."""
    for block in note.body.blocks:
        if block.label and block.label.name == label:
            return block
    return None


def find_heading_by_slug(note: Note, slug: str) -> Block | None:
    """Find a heading block with the given slug."""
    for block in note.body.blocks:
        if block.kind == "heading" and block.heading_slug == slug:
            return block
    return None


def slice_heading(note: Note, heading_block: Block) -> tuple[int, int]:
    """
    Get the range for a heading slice.
    
    Returns from heading start to next heading of same/higher level (or EOF).
    """
    if heading_block.kind != "heading" or heading_block.heading_level is None:
        # Fallback to just the block range
        return (heading_block.range.start, heading_block.range.end)
    
    start = heading_block.range.start
    level = heading_block.heading_level
    
    # Find next heading of same or higher level
    found_current = False
    for block in note.body.blocks:
        if block == heading_block:
            found_current = True
            continue
        
        if found_current and block.kind == "heading" and block.heading_level is not None:
            if block.heading_level <= level:
                # Found next heading at same or higher level
                return (start, block.range.start)
    
    # No next heading found, go to end of note
    return (start, len(note.body.raw))


def slice_block(note: Note, block: Block) -> tuple[int, int]:
    """
    Get the range for a block slice.
    
    - If block is a heading: use heading slice rules
    - Otherwise: return exact block range
    """
    if block.kind == "heading":
        return slice_heading(note, block)
    else:
        # For fence or other blocks, return exact range
        return (block.range.start, block.range.end)


def slice_by_anchor(note: Note, anchor: Anchor | None) -> tuple[int, int]:
    """
    Get the range to slice based on anchor.
    
    - No anchor: return entire body (no frontmatter)
    - Block anchor (^label): find labeled block and slice it
    - Heading anchor (slug): find heading and slice it
    
    Returns (start, end) character offsets.
    """
    if anchor is None:
        # Return entire body - need to skip frontmatter if present
        # Frontmatter is delimited by --- at start and end
        text = note.body.raw
        if text.startswith("---"):
            # Find end of frontmatter
            lines = text.split('\n')
            for i in range(1, len(lines)):
                if lines[i].strip() == "---":
                    # Skip to after the second ---
                    start = sum(len(line) + 1 for line in lines[:i+1])
                    return (start, len(text))
        return (0, len(text))
    
    if anchor.kind == "block":
        # Find labeled block
        block = find_label(note, anchor.value)
        if block is None:
            # Return empty range if not found
            return (0, 0)
        return slice_block(note, block)
    
    elif anchor.kind == "heading":
        # Find heading by slug
        block = find_heading_by_slug(note, anchor.value)
        if block is None:
            # Return empty range if not found
            return (0, 0)
        return slice_heading(note, block)
    
    # Unknown anchor kind
    return (0, 0)
