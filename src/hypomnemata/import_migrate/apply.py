"""Apply phase: execute import with file operations."""

import json
import os
import shutil
from pathlib import Path
from typing import Literal

import yaml

from .models import ImportManifest, ImportPlan, ManifestEntry


def inject_frontmatter(
    content: str,
    note_id: str,
    title: str,
    aliases: list[str] | None = None,
) -> str:
    """
    Inject or update frontmatter with id, title, and aliases.
    
    Args:
        content: Original file content
        note_id: Note ID to inject
        title: Title to inject
        aliases: Optional list of aliases
    
    Returns:
        Content with updated frontmatter
    """
    # Parse existing frontmatter if present
    existing_meta = {}
    body_start = 0
    
    if content.startswith("---\n"):
        end_idx = content.find("\n---\n", 4)
        if end_idx > 0:
            frontmatter_str = content[4:end_idx]
            try:
                existing_meta = yaml.safe_load(frontmatter_str) or {}
            except yaml.YAMLError:
                existing_meta = {}
            body_start = end_idx + 5
    
    # Update metadata
    existing_meta["id"] = note_id
    existing_meta["core/title"] = title
    if aliases:
        existing_meta["core/aliases"] = aliases
    
    # Reconstruct file
    frontmatter_str = yaml.dump(existing_meta, default_flow_style=False, allow_unicode=True)
    body = content[body_start:]
    
    return f"---\n{frontmatter_str}---\n{body}"


def apply_import(
    plan: ImportPlan,
    dst_vault: Path,
    operation: Literal["move", "copy"] = "copy",
    dry_run: bool = False,
    on_conflict: Literal["skip", "new-id", "fail"] = "fail",
) -> ImportManifest:
    """
    Execute import based on plan.
    
    Args:
        plan: Import plan to execute
        dst_vault: Destination vault directory
        operation: Whether to move or copy files
        dry_run: If True, don't actually perform operations
        on_conflict: How to handle existing files
    
    Returns:
        ImportManifest for rollback
    """
    manifest = ImportManifest(
        src_dir=plan.src,
        dst_vault=str(dst_vault.absolute()),
        operation=operation,
    )
    
    src_dir = Path(plan.src)
    
    # Ensure destination exists
    if not dry_run:
        dst_vault.mkdir(parents=True, exist_ok=True)
    
    # Process each item
    for item in plan.items:
        if item.status != "ok":
            # Skip items with errors or conflicts
            continue
        
        src_path = src_dir / item.src
        dst_path = dst_vault / f"{item.id}.md"
        
        # Check for conflicts
        if dst_path.exists():
            if on_conflict == "skip":
                continue
            elif on_conflict == "fail":
                raise FileExistsError(f"Destination already exists: {dst_path}")
            elif on_conflict == "new-id":
                # Generate a new ID (simple increment suffix)
                base_id = item.id
                counter = 1
                while dst_path.exists():
                    item.id = f"{base_id}_{counter}"
                    dst_path = dst_vault / f"{item.id}.md"
                    counter += 1
        
        # Read source file
        if not src_path.exists():
            raise FileNotFoundError(f"Source file not found: {src_path}")
        
        content = src_path.read_text(encoding='utf-8')
        
        # Inject frontmatter
        updated_content = inject_frontmatter(
            content,
            item.id,
            item.title,
            item.aliases if item.aliases else None,
        )
        
        if dry_run:
            print(f"[DRY RUN] Would {operation}: {src_path} -> {dst_path}")
            continue
        
        # Create backup if overwriting
        backup_path = None
        if dst_path.exists():
            backup_path = dst_path.with_suffix(f".bak~{os.getpid()}")
            shutil.copy2(dst_path, backup_path)
        
        # Write to destination (atomic via temp file)
        tmp_path = dst_path.with_suffix(".tmp")
        tmp_path.write_text(updated_content, encoding='utf-8')
        tmp_path.replace(dst_path)
        
        # Record manifest entry
        manifest.entries.append(ManifestEntry(
            action=operation,  # type: ignore
            src=str(src_path) if operation in ("move", "copy") else None,
            dst=str(dst_path),
            backup=str(backup_path) if backup_path else None,
        ))
        
        # Remove source if moving
        if operation == "move":
            src_path.unlink()
    
    return manifest


def save_manifest(manifest: ImportManifest, output_path: Path) -> None:
    """Save manifest to JSON file."""
    data = {
        "version": manifest.version,
        "timestamp": manifest.timestamp,
        "src_dir": manifest.src_dir,
        "dst_vault": manifest.dst_vault,
        "operation": manifest.operation,
        "entries": [
            {
                "action": entry.action,
                "src": entry.src,
                "dst": entry.dst,
                "backup": entry.backup,
            }
            for entry in manifest.entries
        ],
    }
    
    with output_path.open('w', encoding='utf-8') as f:
        json.dump(data, f, indent=2, ensure_ascii=False)


def load_manifest(input_path: Path) -> ImportManifest:
    """Load manifest from JSON file."""
    with input_path.open('r', encoding='utf-8') as f:
        data = json.load(f)
    
    manifest = ImportManifest(
        version=data.get("version", 1),
        timestamp=data.get("timestamp", ""),
        src_dir=data.get("src_dir", ""),
        dst_vault=data.get("dst_vault", ""),
        operation=data.get("operation", "copy"),
    )
    
    for entry_data in data.get("entries", []):
        manifest.entries.append(ManifestEntry(
            action=entry_data["action"],
            src=entry_data.get("src"),
            dst=entry_data["dst"],
            backup=entry_data.get("backup"),
        ))
    
    return manifest
