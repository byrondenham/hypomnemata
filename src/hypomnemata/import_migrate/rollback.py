"""Rollback functionality for import operations."""

import shutil
from pathlib import Path

from .apply import load_manifest
from .models import ImportManifest


def rollback_import(manifest: ImportManifest, dry_run: bool = False) -> None:
    """
    Rollback import operations based on manifest.
    
    Args:
        manifest: Import manifest to rollback
        dry_run: If True, don't actually perform operations
    """
    # Process entries in reverse order
    for entry in reversed(manifest.entries):
        dst_path = Path(entry.dst)
        
        if entry.action == "create":
            # Remove created file
            if dry_run:
                print(f"[DRY RUN] Would remove: {dst_path}")
            else:
                if dst_path.exists():
                    dst_path.unlink()
                    print(f"Removed: {dst_path}")
        
        elif entry.action == "move":
            # Move back to original location
            if entry.src:
                src_path = Path(entry.src)
                if dry_run:
                    print(f"[DRY RUN] Would move back: {dst_path} -> {src_path}")
                else:
                    if dst_path.exists():
                        # Ensure parent directory exists
                        src_path.parent.mkdir(parents=True, exist_ok=True)
                        shutil.move(str(dst_path), str(src_path))
                        print(f"Moved back: {dst_path} -> {src_path}")
        
        elif entry.action == "copy":
            # Remove copied file and restore backup if exists
            if dry_run:
                print(f"[DRY RUN] Would remove copy: {dst_path}")
                if entry.backup:
                    print(f"[DRY RUN] Would restore backup: {entry.backup} -> {dst_path}")
            else:
                if dst_path.exists():
                    dst_path.unlink()
                    print(f"Removed: {dst_path}")
                
                # Restore backup if it exists
                if entry.backup:
                    backup_path = Path(entry.backup)
                    if backup_path.exists():
                        shutil.copy2(backup_path, dst_path)
                        backup_path.unlink()
                        print(f"Restored backup: {entry.backup} -> {dst_path}")


def rollback_from_file(manifest_path: Path, dry_run: bool = False) -> None:
    """
    Load manifest from file and rollback.
    
    Args:
        manifest_path: Path to manifest JSON file
        dry_run: If True, don't actually perform operations
    """
    manifest = load_manifest(manifest_path)
    rollback_import(manifest, dry_run=dry_run)
