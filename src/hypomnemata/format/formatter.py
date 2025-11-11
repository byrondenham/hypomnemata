"""Main formatter driver for Hypomnemata notes."""

import hashlib
from dataclasses import dataclass
from pathlib import Path

from .fm import normalize_frontmatter
from .links import normalize_links
from .text import normalize_text


@dataclass
class FormatOptions:
    """Options for note formatting."""
    
    # Frontmatter options
    frontmatter: bool = True
    key_order: list[str] | None = None
    sort_keys: bool = True
    
    # Link options
    links: bool = True
    ids_only: bool = False
    
    # Text hygiene options
    wrap: int = 0
    eol: str | None = None
    strip_trailing: bool = True
    ensure_final_eol: bool = True


@dataclass
class FormatResult:
    """Result of formatting a note."""
    
    note_id: str
    changed: bool
    changes: list[str]  # List of change types: "frontmatter", "links", "whitespace"
    original_text: str
    formatted_text: str


def format_note(
    note_id: str,
    raw_text: str,
    options: FormatOptions | None = None,
) -> FormatResult:
    """Format a note according to options.
    
    Args:
        note_id: The note ID (filename stem)
        raw_text: The full note content
        options: Formatting options
    
    Returns:
        FormatResult with formatted text and change information
    """
    if options is None:
        options = FormatOptions()
    
    original = raw_text
    result = raw_text
    changes = []
    
    # Step 1: Normalize frontmatter
    if options.frontmatter:
        formatted_fm = normalize_frontmatter(
            result,
            note_id,
            key_order=options.key_order,
            sort_keys=options.sort_keys,
        )
        if formatted_fm != result:
            changes.append("frontmatter")
            result = formatted_fm
    
    # Step 2: Normalize links
    if options.links:
        # Only normalize body, not frontmatter
        import re
        fm_match = re.match(r"^\s*---\s*\n.*?\n---\s*\n+", result, re.DOTALL)
        if fm_match:
            fm_part = result[:fm_match.end()]
            body_part = result[fm_match.end():]
        else:
            fm_part = ""
            body_part = result
        
        formatted_body = normalize_links(body_part, ids_only=options.ids_only)
        if formatted_body != body_part:
            changes.append("links")
        
        result = fm_part + formatted_body
    
    # Step 3: Text hygiene
    if options.wrap > 0 or options.eol or options.strip_trailing or options.ensure_final_eol:
        # Only apply to body, not frontmatter
        import re
        fm_match = re.match(r"^\s*---\s*\n.*?\n---\s*\n+", result, re.DOTALL)
        if fm_match:
            fm_part = result[:fm_match.end()]
            body_part = result[fm_match.end():]
        else:
            fm_part = ""
            body_part = result
        
        formatted_body = normalize_text(
            body_part,
            wrap=options.wrap,
            eol=options.eol,
            strip_trailing=options.strip_trailing,
            ensure_final_eol=options.ensure_final_eol,
        )
        if formatted_body != body_part:
            changes.append("whitespace")
        
        result = fm_part + formatted_body
    
    changed = result != original
    
    return FormatResult(
        note_id=note_id,
        changed=changed,
        changes=changes,
        original_text=original,
        formatted_text=result,
    )


def format_file(
    file_path: Path,
    options: FormatOptions | None = None,
    dry_run: bool = True,
) -> FormatResult:
    """Format a note file.
    
    Args:
        file_path: Path to the note file
        options: Formatting options
        dry_run: If True, don't write changes
    
    Returns:
        FormatResult
    """
    # Extract note ID from filename
    note_id = file_path.stem
    
    # Read file
    raw_text = file_path.read_text(encoding='utf-8')
    
    # Format
    result = format_note(note_id, raw_text, options)
    
    # Write if not dry run and changed
    if not dry_run and result.changed:
        # Atomic write using temp file
        tmp_path = file_path.with_suffix('.md.tmp')
        try:
            tmp_path.write_text(result.formatted_text, encoding='utf-8')
            tmp_path.replace(file_path)
        except Exception:
            # Clean up temp file on error
            if tmp_path.exists():
                tmp_path.unlink()
            raise
    
    return result


def compute_file_hash(file_path: Path) -> str:
    """Compute SHA256 hash of file content."""
    content = file_path.read_bytes()
    return hashlib.sha256(content).hexdigest()
