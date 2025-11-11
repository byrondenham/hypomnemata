"""Tests for watch mode functionality."""

import tempfile
import time
from pathlib import Path
from threading import Thread

import pytest

from hypomnemata.adapters.fs_storage import FsStorage
from hypomnemata.adapters.markdown_parser import MarkdownParser
from hypomnemata.adapters.sqlite_index import SQLiteIndex
from hypomnemata.adapters.yaml_codec import MarkdownNoteCodec, YamlFrontmatter
from hypomnemata.core.meta import MetaBag
from hypomnemata.core.model import Note
from hypomnemata.core.vault import Vault

try:
    from hypomnemata.watch import watch_vault, WATCHDOG_AVAILABLE
except ImportError:
    WATCHDOG_AVAILABLE = False


@pytest.fixture
def temp_vault():
    """Create a temporary vault for testing."""
    with tempfile.TemporaryDirectory() as tmpdir:
        vault_path = Path(tmpdir) / "vault"
        vault_path.mkdir()
        
        storage = FsStorage(vault_path)
        codec = MarkdownNoteCodec(YamlFrontmatter())
        parser = MarkdownParser()
        vault = Vault(storage, parser, codec)
        
        db_path = Path(tmpdir) / "test.db"
        index = SQLiteIndex(db_path=db_path, vault_path=vault_path, vault=vault)
        
        yield vault, index, vault_path


@pytest.mark.skipif(not WATCHDOG_AVAILABLE, reason="watchdog not installed")
def test_update_notes_incremental():
    """Test SQLiteIndex.update_notes() method."""
    with tempfile.TemporaryDirectory() as tmpdir:
        vault_path = Path(tmpdir) / "vault"
        vault_path.mkdir()
        
        storage = FsStorage(vault_path)
        codec = MarkdownNoteCodec(YamlFrontmatter())
        parser = MarkdownParser()
        vault = Vault(storage, parser, codec)
        
        db_path = Path(tmpdir) / "test.db"
        index = SQLiteIndex(db_path=db_path, vault_path=vault_path, vault=vault)
        
        # Create initial notes
        note1 = Note(
            id="note1",
            meta=MetaBag({"title": "First"}),
            body=parser.parse("# First\n\nContent.", "note1")
        )
        note2 = Note(
            id="note2",
            meta=MetaBag({"title": "Second"}),
            body=parser.parse("# Second\n\nContent.", "note2")
        )
        
        vault.put(note1)
        vault.put(note2)
        
        # Initial build
        index.rebuild(full=True)
        
        # Create a new note
        note3 = Note(
            id="note3",
            meta=MetaBag({"title": "Third"}),
            body=parser.parse("# Third\n\nNew content.", "note3")
        )
        vault.put(note3)
        
        # Update using update_notes
        counts = index.update_notes(changed={"note3"}, deleted=set())
        
        assert counts["inserted"] == 1
        assert counts["updated"] == 0
        assert counts["removed"] == 0
        
        # Verify note3 is in index
        conn = index._conn()
        try:
            row = conn.execute("SELECT title FROM notes WHERE id = ?", ("note3",)).fetchone()
            assert row is not None
            assert row[0] == "Third"
        finally:
            conn.close()


@pytest.mark.skipif(not WATCHDOG_AVAILABLE, reason="watchdog not installed")
def test_update_notes_deletion():
    """Test SQLiteIndex.update_notes() handles deletions."""
    with tempfile.TemporaryDirectory() as tmpdir:
        vault_path = Path(tmpdir) / "vault"
        vault_path.mkdir()
        
        storage = FsStorage(vault_path)
        codec = MarkdownNoteCodec(YamlFrontmatter())
        parser = MarkdownParser()
        vault = Vault(storage, parser, codec)
        
        db_path = Path(tmpdir) / "test.db"
        index = SQLiteIndex(db_path=db_path, vault_path=vault_path, vault=vault)
        
        # Create notes
        note1 = Note(
            id="note1",
            meta=MetaBag({"title": "First"}),
            body=parser.parse("# First", "note1")
        )
        vault.put(note1)
        
        # Build index
        index.rebuild(full=True)
        
        # Delete using update_notes
        counts = index.update_notes(changed=set(), deleted={"note1"})
        
        assert counts["removed"] == 1
        
        # Verify note1 is gone
        conn = index._conn()
        try:
            row = conn.execute("SELECT id FROM notes WHERE id = ?", ("note1",)).fetchone()
            assert row is None
        finally:
            conn.close()


@pytest.mark.skipif(not WATCHDOG_AVAILABLE, reason="watchdog not installed")
def test_update_notes_modification():
    """Test SQLiteIndex.update_notes() handles modifications."""
    with tempfile.TemporaryDirectory() as tmpdir:
        vault_path = Path(tmpdir) / "vault"
        vault_path.mkdir()
        
        storage = FsStorage(vault_path)
        codec = MarkdownNoteCodec(YamlFrontmatter())
        parser = MarkdownParser()
        vault = Vault(storage, parser, codec)
        
        db_path = Path(tmpdir) / "test.db"
        index = SQLiteIndex(db_path=db_path, vault_path=vault_path, vault=vault)
        
        # Create note
        note1 = Note(
            id="note1",
            meta=MetaBag({"title": "Original"}),
            body=parser.parse("# Original", "note1")
        )
        vault.put(note1)
        
        # Build index
        index.rebuild(full=True)
        
        # Modify note
        time.sleep(0.01)
        note1_modified = Note(
            id="note1",
            meta=MetaBag({"title": "Modified"}),
            body=parser.parse("# Modified", "note1")
        )
        vault.put(note1_modified)
        
        # Update using update_notes
        counts = index.update_notes(changed={"note1"}, deleted=set())
        
        assert counts["updated"] == 1
        assert counts["inserted"] == 0
        
        # Verify title changed
        conn = index._conn()
        try:
            row = conn.execute("SELECT title FROM notes WHERE id = ?", ("note1",)).fetchone()
            assert row is not None
            assert row[0] == "Modified"
        finally:
            conn.close()


@pytest.mark.skipif(not WATCHDOG_AVAILABLE, reason="watchdog not installed")
def test_watch_skip_temp_files(temp_vault):
    """Test that watch mode skips temp and swap files."""
    from hypomnemata.watch import DebounceHandler
    
    vault, index, vault_path = temp_vault
    
    events_received = []
    
    def on_batch(changed, deleted):
        events_received.append((changed, deleted))
    
    handler = DebounceHandler(vault_path, on_batch, debounce_ms=50)
    
    # Test various temp file patterns
    temp_files = [
        vault_path / "test.swp",
        vault_path / "test~",
        vault_path / ".#test.md",
        vault_path / ".hidden.md",
    ]
    
    # Create files
    for temp_file in temp_files:
        temp_file.write_text("temp content")
        # Simulate events
        assert handler._should_skip(temp_file)
    
    # Should skip all these files
    assert len(handler.added) == 0
    assert len(handler.modified) == 0
    assert len(handler.deleted) == 0


@pytest.mark.skipif(not WATCHDOG_AVAILABLE, reason="watchdog not installed")
def test_watch_debounce():
    """Test that debouncing coalesces multiple events."""
    from hypomnemata.watch import DebounceHandler
    
    with tempfile.TemporaryDirectory() as tmpdir:
        vault_path = Path(tmpdir)
        
        events_received = []
        
        def on_batch(changed, deleted):
            events_received.append((set(changed), set(deleted)))
        
        handler = DebounceHandler(vault_path, on_batch, debounce_ms=100)
        
        # Simulate multiple events for same file
        handler.added.add("note1")
        handler.modified.add("note1")
        handler.modified.add("note2")
        
        # Don't wait for debounce, manually flush
        handler.flush()
        
        # Should get one batch with combined events
        assert len(events_received) == 1
        changed, deleted = events_received[0]
        
        # note1 should be in changed (added + modified coalesced)
        assert "note1" in changed
        assert "note2" in changed
        assert len(deleted) == 0
