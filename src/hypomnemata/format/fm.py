"""Frontmatter normalization for Hypomnemata notes."""

import io
from typing import Any

import yaml


def normalize_frontmatter(
    raw_text: str,
    note_id: str,
    key_order: list[str] | None = None,
    sort_keys: bool = True,
) -> str:
    """Normalize YAML frontmatter in a note.
    
    Args:
        raw_text: Full note text (frontmatter + body)
        note_id: The note's ID (filename stem) to enforce in frontmatter
        key_order: Optional preferred order for keys. Default: ["id", "core/title", "core/aliases"]
        sort_keys: Sort remaining keys alphabetically
    
    Returns:
        Normalized note text with canonical frontmatter
    """
    # Default key ordering
    if key_order is None:
        key_order = ["id", "core/title", "core/aliases"]
    
    # Extract frontmatter and body
    import re
    fm_match = re.match(r"^\s*---\s*\n(.*?)\n---\s*\n?", raw_text, re.DOTALL)
    
    if fm_match:
        # Parse existing frontmatter
        fm_yaml = fm_match.group(1)
        try:
            meta = yaml.safe_load(io.StringIO(fm_yaml)) or {}
        except yaml.YAMLError:
            # If YAML is invalid, keep original
            return raw_text
        
        body = raw_text[fm_match.end():]
    else:
        # No frontmatter exists
        meta = {}
        body = raw_text
    
    # Ensure id matches filename
    meta["id"] = note_id
    
    # Sort keys according to preferred order
    ordered_meta: dict[str, Any] = {}
    
    # Add keys in preferred order first
    for key in key_order:
        if key in meta:
            ordered_meta[key] = meta[key]
    
    # Add remaining keys
    remaining_keys = [k for k in meta.keys() if k not in key_order]
    if sort_keys:
        remaining_keys = sorted(remaining_keys)
    
    for key in remaining_keys:
        ordered_meta[key] = meta[key]
    
    # Encode frontmatter
    if not ordered_meta:
        # No metadata, return just body
        return body
    
    fm_buf = io.StringIO()
    yaml.safe_dump(ordered_meta, fm_buf, sort_keys=False, allow_unicode=True)
    fm_str = fm_buf.getvalue()
    
    # Ensure exactly one blank line between frontmatter and body
    body_stripped = body.lstrip('\n')
    
    return f"---\n{fm_str}---\n\n{body_stripped}"
