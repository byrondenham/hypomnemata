"""Asset reference scanner for Hypomnemata notes."""

import re
from dataclasses import dataclass
from pathlib import Path


@dataclass
class AssetRef:
    """A reference to an asset file."""
    
    note_id: str
    asset_path: str  # As written in the note
    resolved_path: Path | None  # Resolved absolute path
    ref_type: str  # "image", "file", "html"
    range_start: int | None = None
    range_end: int | None = None


def scan_asset_refs(
    note_id: str,
    note_text: str,
    vault_root: Path,
    assets_dir: Path | None = None,
) -> list[AssetRef]:
    """Scan a note for asset references.
    
    Args:
        note_id: The note ID
        note_text: The note content
        vault_root: Root directory of the vault
        assets_dir: Assets directory (default: vault_root/assets)
    
    Returns:
        List of asset references found in the note
    """
    if assets_dir is None:
        assets_dir = vault_root / "assets"
    
    refs = []
    seen_ranges: set[tuple[int, int]] = set()  # Track ranges to avoid duplicates
    
    # Extract Markdown images: ![alt](path)
    img_pattern = re.compile(r'!\[([^\]]*)\]\(([^)]+)\)')
    for match in img_pattern.finditer(note_text):
        path_str = match.group(2).strip()
        
        # Skip URLs
        if path_str.startswith(('http://', 'https://', '//')):
            continue
        
        # Resolve path
        resolved = _resolve_asset_path(path_str, vault_root, assets_dir)
        
        # Mark both the full match and the inner [...] as seen to avoid duplicates
        seen_ranges.add((match.start(), match.end()))
        seen_ranges.add((match.start() + 1, match.end()))  # Also mark without the !
        
        refs.append(AssetRef(
            note_id=note_id,
            asset_path=path_str,
            resolved_path=resolved,
            ref_type="image",
            range_start=match.start(),
            range_end=match.end(),
        ))
    
    # Extract Markdown file links: [text](path) where path is not http(s)
    link_pattern = re.compile(r'\[([^\]]+)\]\(([^)]+)\)')
    for match in link_pattern.finditer(note_text):
        path_str = match.group(2).strip()
        
        # Skip URLs and anchors
        if path_str.startswith(('http://', 'https://', '//', '#')):
            continue
        
        # Skip wiki-style links (already handled by link parser)
        if path_str.startswith('[['):
            continue
        
        # Skip if already seen (from image pattern)
        range_key = (match.start(), match.end())
        if range_key in seen_ranges:
            continue
        
        # Check if it looks like a file reference (has extension)
        if '.' in Path(path_str).name:
            resolved = _resolve_asset_path(path_str, vault_root, assets_dir)
            
            seen_ranges.add(range_key)
            
            refs.append(AssetRef(
                note_id=note_id,
                asset_path=path_str,
                resolved_path=resolved,
                ref_type="file",
                range_start=match.start(),
                range_end=match.end(),
            ))
    
    # Extract HTML img tags: <img src="path" ...>
    html_img_pattern = re.compile(r'<img[^>]+src=["\']([^"\']+)["\'][^>]*>', re.IGNORECASE)
    for match in html_img_pattern.finditer(note_text):
        path_str = match.group(1).strip()
        
        # Skip URLs
        if path_str.startswith(('http://', 'https://', '//', 'data:')):
            continue
        
        resolved = _resolve_asset_path(path_str, vault_root, assets_dir)
        
        refs.append(AssetRef(
            note_id=note_id,
            asset_path=path_str,
            resolved_path=resolved,
            ref_type="html",
            range_start=match.start(),
            range_end=match.end(),
        ))
    
    return refs


def _resolve_asset_path(
    path_str: str,
    vault_root: Path,
    assets_dir: Path,
) -> Path | None:
    """Resolve an asset path to an absolute path.
    
    Args:
        path_str: The path as written in the note
        vault_root: Vault root directory
        assets_dir: Assets directory
    
    Returns:
        Resolved absolute path, or None if cannot resolve
    """
    # Remove any URL fragments or query strings
    path_str = path_str.split('#')[0].split('?')[0]
    
    # Handle absolute paths (relative to vault root)
    if path_str.startswith('/'):
        return (vault_root / path_str[1:]).resolve()
    
    # Handle relative paths
    path = Path(path_str)
    
    # If it starts with ./ or ../, resolve relative to vault root
    if path_str.startswith(('./', '../')):
        return (vault_root / path).resolve()
    
    # If path starts with "assets/", resolve relative to vault root (not assets_dir)
    # This avoids creating assets/assets/...
    if path_str.startswith('assets/'):
        return (vault_root / path).resolve()
    
    # Otherwise, assume it's relative to assets directory
    return (assets_dir / path).resolve()
