"""Utilities for locating notes and anchors with precise character and line positions."""

import json
import sys
from typing import Any

from .core.model import Anchor, Note
from .core.slicer import slice_by_anchor


def char_offset_to_line(text: str, offset: int) -> int:
    """
    Convert character offset to line number (1-based).
    
    Args:
        text: The full text
        offset: Character offset (0-based)
    
    Returns:
        Line number (1-based)
    """
    if offset == 0:
        return 1
    
    # Count newlines up to offset
    line = 1
    for i in range(min(offset, len(text))):
        if text[i] == '\n':
            line += 1
    
    return line


def locate_note(
    note: Note,
    anchor: Anchor | None,
    format_type: str = "json",
    context: int = 0,
) -> dict[str, Any] | str:
    """
    Get precise location information for a note or anchor.
    
    Args:
        note: The note to locate
        anchor: Optional anchor (heading or block)
        format_type: Output format ("json" or "tsv")
        context: Number of context lines (unused, reserved for future)
    
    Returns:
        Location information as dict (for JSON) or TSV string
    """
    # Get the range for the note/anchor
    start, end = slice_by_anchor(note, anchor)
    
    # If range is empty, anchor wasn't found
    if start == end and anchor is not None:
        return {}
    
    # Convert offsets to line numbers
    start_line = char_offset_to_line(note.body.raw, start)
    end_line = char_offset_to_line(note.body.raw, end)
    
    # Build result
    result = {
        "id": note.id,
        "range": {"start": start, "end": end},
        "lines": {"start": start_line, "end": end_line},
    }
    
    # Add anchor info if present
    if anchor:
        result["anchor"] = {
            "kind": anchor.kind,
            "value": anchor.value,
        }
    
    if format_type == "tsv":
        # Format as tab-separated values
        return f"{note.id}\t{start}\t{end}\t{start_line}\t{end_line}"
    
    return result


def cmd_locate(args: Any, rt: Any) -> int:
    """
    Locate command handler.
    
    Args:
        args: Parsed command-line arguments
        rt: Runtime instance
    
    Returns:
        Exit code
    """
    # Parse ref into id and optional anchor
    ref = args.ref
    anchor = None
    
    if "#" in ref:
        nid, anchor_str = ref.split("#", 1)
        if anchor_str.startswith("^"):
            # Block label
            anchor = Anchor(kind="block", value=anchor_str[1:])
        else:
            # Heading slug
            anchor = Anchor(kind="heading", value=anchor_str)
    else:
        nid = ref
    
    # Get note
    note = rt.vault.get(nid)
    if note is None:
        print(f"Note {nid} not found", file=sys.stderr)
        return 1
    
    # Get absolute path to the note file
    note_path = rt.vault.storage._path(nid)
    
    # Get location information
    format_type = getattr(args, "format", "json")
    context = getattr(args, "context", 0)
    
    location = locate_note(note, anchor, format_type, context)
    
    # Check if anchor was not found
    if not location:
        if anchor:
            anchor_repr = f"^{anchor.value}" if anchor.kind == "block" else anchor.value
            print(f"Anchor #{anchor_repr} not found in note {nid}", file=sys.stderr)
        else:
            print(f"Could not locate note {nid}", file=sys.stderr)
        return 1
    
    # Add path to result (absolute path)
    if format_type == "json":
        location["path"] = str(note_path.absolute())
        print(json.dumps(location, indent=2))
    else:
        # TSV format: id, path, start, end, start_line, end_line
        print(f"{nid}\t{note_path.absolute()}\t{location}", end="")
    
    return 0
