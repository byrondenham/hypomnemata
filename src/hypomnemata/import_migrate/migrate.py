"""Link migration: convert wiki/MD links to ID-based links."""

import re
from dataclasses import dataclass
from pathlib import Path

from ..adapters.sqlite_index import SQLiteIndex


@dataclass
class LinkMigrationResult:
    """Result of migrating links in a file."""
    
    path: str
    original: str
    migrated: str
    changes: int
    errors: list[str]


def resolve_target(
    text: str,
    index: SQLiteIndex,
    resolver_mode: str = "both",
    prefer: str = "alias",
) -> str | None:
    """
    Resolve text to note ID via index.
    
    Args:
        text: Text to resolve (title or alias)
        index: SQLite index
        resolver_mode: "title", "alias", or "both"
        prefer: "title" or "alias" (when both match)
    
    Returns:
        Note ID if found, None if not found or ambiguous
    """
    conn = index._conn()
    try:
        # Check aliases
        alias_ids: list[str] = []
        if resolver_mode in ("alias", "both"):
            alias_rows = conn.execute(
                "SELECT note_id FROM kv WHERE key = 'core/alias' AND value = ?",
                (text,)
            ).fetchall()
            alias_ids = [str(row[0]) for row in alias_rows]
        
        # Check titles
        title_ids: list[str] = []
        if resolver_mode in ("title", "both"):
            title_rows = conn.execute(
                "SELECT id FROM notes WHERE title = ?",
                (text,)
            ).fetchall()
            title_ids = [str(row[0]) for row in title_rows]
        
        # Determine result
        if len(alias_ids) == 1 and not title_ids:
            return alias_ids[0]
        elif len(title_ids) == 1 and not alias_ids:
            return title_ids[0]
        elif len(alias_ids) == 1 and len(title_ids) == 1:
            # Both match - use preference
            if prefer == "alias":
                return alias_ids[0]
            else:
                return title_ids[0]
        elif (len(alias_ids) + len(title_ids)) == 0:
            return None  # Not found
        else:
            return None  # Ambiguous (multiple matches)
    finally:
        conn.close()


def migrate_wiki_links(
    content: str,
    index: SQLiteIndex,
    resolver_mode: str = "both",
    prefer: str = "alias",
) -> tuple[str, list[str]]:
    """
    Migrate Obsidian-style wiki links to ID-based format.
    
    Handles:
    - [[Title]] -> [[id]]
    - [[Title|Display]] -> [[id|Display]]
    - [[Title#Heading]] -> [[id#heading]]
    - ![[Title]] -> ![[id]]
    - ![[Title#^label]] -> ![[id#^label]]
    
    Returns:
        Tuple of (migrated_content, errors)
    """
    errors: list[str] = []
    
    # Pattern for wiki links: [[...]]
    # Matches: [[Title]], [[Title|Display]], [[Title#Anchor]]
    wiki_pattern = re.compile(r'(!?)\[\[([^\]]+?)\]\]')
    
    def replace_wiki_link(match: re.Match[str]) -> str:
        transclude = match.group(1)  # ! if transclusion
        inner = match.group(2)  # Content inside [[...]]
        
        # Parse inner: could be "Title", "Title|Display", "Title#Anchor", etc.
        display_text = None
        anchor = None
        
        # Check for display text: [[Title|Display]]
        if '|' in inner:
            target_part, display_text = inner.split('|', 1)
        else:
            target_part = inner
        
        # Check for anchor: Title#Anchor
        if '#' in target_part:
            title_part, anchor = target_part.split('#', 1)
        else:
            title_part = target_part
        
        # Resolve title to ID
        note_id = resolve_target(title_part.strip(), index, resolver_mode, prefer)
        
        if note_id is None:
            errors.append(f"Could not resolve: '{title_part.strip()}'")
            return match.group(0)  # Return original
        
        # Reconstruct link with ID
        new_inner = note_id
        if anchor:
            new_inner += f"#{anchor}"
        if display_text:
            new_inner += f"|{display_text}"
        
        return f"{transclude}[[{new_inner}]]"
    
    migrated = wiki_pattern.sub(replace_wiki_link, content)
    return migrated, errors


def migrate_md_links(
    content: str,
    index: SQLiteIndex,
    vault_path: Path,
    current_file_path: Path,
    resolver_mode: str = "both",
    prefer: str = "alias",
) -> tuple[str, list[str]]:
    """
    Migrate Markdown-style links to ID-based format.
    
    Handles:
    - [Text](path/to/file.md) -> [Text](id)
    - [Text](path/to/file.md#heading) -> [Text](id#heading)
    
    Returns:
        Tuple of (migrated_content, errors)
    """
    errors: list[str] = []
    
    # Pattern for markdown links: [text](path)
    md_pattern = re.compile(r'\[([^\]]+)\]\(([^)]+)\)')
    
    def replace_md_link(match: re.Match[str]) -> str:
        link_text = match.group(1)
        link_path = match.group(2)
        
        # Skip external links (http://, https://, etc.)
        if link_path.startswith(('http://', 'https://', 'mailto:', 'ftp://')):
            return match.group(0)
        
        # Parse path and anchor
        anchor = None
        if '#' in link_path:
            path_part, anchor = link_path.split('#', 1)
        else:
            path_part = link_path
        
        # Resolve relative path to absolute
        if path_part.startswith('/'):
            # Absolute from vault root
            target_path = vault_path / path_part.lstrip('/')
        else:
            # Relative to current file
            target_path = (current_file_path.parent / path_part).resolve()
        
        # Extract note ID from target path (assuming <id>.md format)
        if target_path.suffix == '.md':
            # Try to extract ID from filename
            note_id = target_path.stem
            
            # Verify ID exists in index
            conn = index._conn()
            try:
                row = conn.execute(
                    "SELECT id FROM notes WHERE id = ?",
                    (note_id,)
                ).fetchone()
                
                if row is None:
                    errors.append(f"Note ID not found: {note_id} (from path: {path_part})")
                    return match.group(0)
            finally:
                conn.close()
            
            # Reconstruct link with ID
            new_path = note_id
            if anchor:
                new_path += f"#{anchor}"
            
            return f"[{link_text}]({new_path})"
        
        # Not a .md file, keep original
        return match.group(0)
    
    migrated = md_pattern.sub(replace_md_link, content)
    return migrated, errors


def migrate_file_links(
    file_path: Path,
    vault_path: Path,
    index: SQLiteIndex,
    from_format: str = "mixed",
    resolver_mode: str = "both",
    prefer: str = "alias",
) -> LinkMigrationResult:
    """
    Migrate all links in a file.
    
    Args:
        file_path: Path to file
        vault_path: Vault root path
        index: SQLite index
        from_format: "wiki", "md", or "mixed"
        resolver_mode: "title", "alias", or "both"
        prefer: "title" or "alias"
    
    Returns:
        LinkMigrationResult
    """
    content = file_path.read_text(encoding='utf-8')
    original = content
    all_errors: list[str] = []
    
    # Migrate wiki links
    if from_format in ("wiki", "mixed"):
        content, wiki_errors = migrate_wiki_links(content, index, resolver_mode, prefer)
        all_errors.extend(wiki_errors)
    
    # Migrate MD links
    if from_format in ("md", "mixed"):
        content, md_errors = migrate_md_links(
            content, index, vault_path, file_path, resolver_mode, prefer
        )
        all_errors.extend(md_errors)
    
    # Count changes (simple heuristic: compare content)
    changes = 1 if content != original else 0
    
    return LinkMigrationResult(
        path=str(file_path),
        original=original,
        migrated=content,
        changes=changes,
        errors=all_errors,
    )


def apply_migration(
    result: LinkMigrationResult,
    dry_run: bool = False,
) -> None:
    """
    Apply migration result to file.
    
    Args:
        result: Migration result
        dry_run: If True, don't actually write
    """
    if dry_run:
        # Print unified diff
        import difflib
        
        diff = difflib.unified_diff(
            result.original.splitlines(keepends=True),
            result.migrated.splitlines(keepends=True),
            fromfile=result.path,
            tofile=result.path,
        )
        print(''.join(diff))
    else:
        # Write migrated content
        file_path = Path(result.path)
        # Atomic write via temp file
        tmp_path = file_path.with_suffix('.tmp')
        tmp_path.write_text(result.migrated, encoding='utf-8')
        tmp_path.replace(file_path)
