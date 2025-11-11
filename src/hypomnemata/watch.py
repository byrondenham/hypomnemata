"""Watch mode for hypomnemata - file watcher with incremental reindexing."""

import json
import signal
import sys
import time
from pathlib import Path
from typing import Any

try:
    from watchdog.events import FileSystemEvent, FileSystemEventHandler
    from watchdog.observers import Observer

    WATCHDOG_AVAILABLE = True
except ImportError:
    WATCHDOG_AVAILABLE = False
    FileSystemEventHandler = object
    FileSystemEvent = Any


class DebounceHandler(FileSystemEventHandler):  # type: ignore[misc]
    """File system event handler with debouncing."""

    def __init__(self, vault_path: Path, on_batch: Any, debounce_ms: int = 150):
        super().__init__()
        self.vault_path = vault_path
        self.on_batch = on_batch
        self.debounce_ms = debounce_ms

        # Track pending changes by ID
        self.added: set[str] = set()
        self.modified: set[str] = set()
        self.deleted: set[str] = set()
        self.last_event_time = 0.0
        self.timer_running = False

    def _should_skip(self, path: Path) -> bool:
        """Check if file should be skipped."""
        name = path.name

        # Skip hidden files
        if name.startswith("."):
            return True

        # Skip temp/swap files
        if name.endswith("~") or name.endswith(".swp") or name.startswith(".#"):
            return True

        # Only process .md files
        if not name.endswith(".md"):
            return True

        return False

    def _extract_id(self, path: Path) -> str | None:
        """Extract note ID from path."""
        if self._should_skip(path):
            return None
        return path.stem

    def on_created(self, event: FileSystemEvent) -> None:
        """Handle file creation."""
        if event.is_directory:
            return

        path = Path(str(event.src_path))
        note_id = self._extract_id(path)
        if note_id:
            self.added.add(note_id)
            self.last_event_time = time.time()

    def on_modified(self, event: FileSystemEvent) -> None:
        """Handle file modification."""
        if event.is_directory:
            return

        path = Path(str(event.src_path))
        note_id = self._extract_id(path)
        if note_id:
            self.modified.add(note_id)
            self.last_event_time = time.time()

    def on_deleted(self, event: FileSystemEvent) -> None:
        """Handle file deletion."""
        if event.is_directory:
            return

        path = Path(str(event.src_path))
        note_id = self._extract_id(path)
        if note_id:
            self.deleted.add(note_id)
            self.last_event_time = time.time()

    def check_and_flush(self) -> None:
        """Check if debounce period has elapsed and flush if so."""
        if not (self.added or self.modified or self.deleted):
            return

        # Check if debounce period has elapsed
        elapsed = (time.time() - self.last_event_time) * 1000
        if elapsed >= self.debounce_ms:
            self.flush()

    def flush(self) -> None:
        """Process accumulated events."""
        if not (self.added or self.modified or self.deleted):
            return

        # Combine added and modified into changed
        changed = self.added | self.modified
        deleted = self.deleted

        # Clear pending events
        self.added.clear()
        self.modified.clear()
        self.deleted.clear()

        # Call batch handler
        if self.on_batch:
            self.on_batch(changed, deleted)


def watch_vault(
    vault_path: Path,
    index: Any,
    debounce_ms: int = 150,
    quiet: bool = False,
    json_output: bool = False,
) -> int:
    """
    Watch vault directory for changes and incrementally reindex.

    Args:
        vault_path: Path to vault directory
        index: SQLiteIndex instance
        debounce_ms: Debounce window in milliseconds
        quiet: Suppress output
        json_output: Output JSON events instead of human-readable

    Returns:
        Exit code
    """
    if not WATCHDOG_AVAILABLE:
        print(
            "Error: watchdog library not installed. Install with: pip install hypomnemata[watch]",
            file=sys.stderr,
        )
        return 1

    if not vault_path.exists():
        print(f"Error: Vault not found: {vault_path}", file=sys.stderr)
        return 1

    # Ensure DB exists
    index._ensure_schema()

    # Check if index is empty and do initial reindex if needed
    from .adapters.sqlite_index import SQLiteIndex

    if isinstance(index, SQLiteIndex):
        conn = index._conn()
        try:
            count = conn.execute("SELECT COUNT(*) FROM notes").fetchone()[0]
            if count == 0 and not quiet:
                if not json_output:
                    print("Index is empty, running initial reindex...")
                counts = index.rebuild(full=True, use_hash=False)
                if not json_output:
                    print(f"Initial reindex complete: {counts['inserted']} notes indexed")
        finally:
            conn.close()

    # Track running state
    running = True

    def handle_batch(changed: set[str], deleted: set[str]) -> None:
        """Handle a batch of changes."""
        start_time = time.time()

        try:
            counts = index.update_notes(changed, deleted)
            duration_ms = int((time.time() - start_time) * 1000)

            if json_output:
                event = {
                    "type": "batch",
                    "added": [nid for nid in changed if counts.get("inserted", 0) > 0],
                    "modified": [nid for nid in changed if counts.get("updated", 0) > 0],
                    "deleted": list(deleted),
                    "duration_ms": duration_ms,
                }
                print(json.dumps(event), flush=True)
            elif not quiet:
                added_count = counts.get("inserted", 0)
                updated_count = counts.get("updated", 0)
                deleted_count = counts.get("removed", 0)
                print(
                    f"Indexed: +{added_count} ~{updated_count} -{deleted_count} ({duration_ms}ms)",
                    flush=True,
                )
        except Exception as e:
            if json_output:
                error_event = {
                    "type": "error",
                    "message": str(e),
                }
                print(json.dumps(error_event), flush=True)
            else:
                print(f"Error: {e}", file=sys.stderr, flush=True)

    # Set up signal handlers for graceful shutdown
    def signal_handler(signum: int, frame: Any) -> None:
        nonlocal running
        running = False
        if not quiet and not json_output:
            print("\nShutting down...", flush=True)

    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)

    # Create observer and handler
    handler = DebounceHandler(vault_path, handle_batch, debounce_ms)
    observer = Observer()
    observer.schedule(handler, str(vault_path), recursive=False)

    if not quiet and not json_output:
        print(f"Watching {vault_path} (debounce: {debounce_ms}ms)", flush=True)
        print("Press Ctrl+C to stop", flush=True)

    # Start observer
    observer.start()

    try:
        # Main loop - check for debounce flush
        while running:
            time.sleep(0.1)  # Check every 100ms
            handler.check_and_flush()
    finally:
        # Flush any pending events before shutdown
        handler.flush()
        observer.stop()
        observer.join()

    if not quiet and not json_output:
        print("Watch stopped", flush=True)

    return 0
