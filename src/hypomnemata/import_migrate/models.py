"""Data models for import/migrate operations."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Literal


@dataclass
class ImportItem:
    """Represents a single item in the import plan."""
    
    src: str  # Source file path (relative or absolute)
    id: str  # Generated ID
    title: str  # Extracted or generated title
    aliases: list[str] = field(default_factory=list)
    status: Literal["ok", "conflict", "error"] = "ok"
    reason: str | None = None  # Error/conflict reason


@dataclass
class ImportPlan:
    """Complete import plan with metadata."""
    
    version: int = 1
    generated_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    src: str = ""  # Source directory path
    id_strategy: Literal["random", "hash", "slug"] = "random"
    items: list[ImportItem] = field(default_factory=list)
    conflicts: dict[str, list[str]] = field(default_factory=dict)  # title/alias -> [paths]


@dataclass
class ManifestEntry:
    """Single entry in import manifest for rollback."""
    
    action: Literal["create", "move", "copy"]  # Operation performed
    src: str | None = None  # Source path (for move/copy)
    dst: str = ""  # Destination path
    backup: str | None = None  # Backup path if file was overwritten


@dataclass
class ImportManifest:
    """Manifest for tracking import operations to enable rollback."""
    
    version: int = 1
    timestamp: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    src_dir: str = ""
    dst_vault: str = ""
    operation: Literal["move", "copy"] = "copy"
    entries: list[ManifestEntry] = field(default_factory=list)
