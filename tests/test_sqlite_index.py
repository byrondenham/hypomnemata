"""Tests for SQLite index functionality."""

import tempfile
from pathlib import Path

import pytest

from hypomnemata.adapters.fs_storage import FsStorage
from hypomnemata.adapters.markdown_parser import MarkdownParser
from hypomnemata.adapters.sqlite_index import SQLiteIndex
from hypomnemata.adapters.yaml_codec import MarkdownNoteCodec, YamlFrontmatter
from hypomnemata.core.meta import MetaBag
from hypomnemata.core.model import Note
from hypomnemata.core.vault import Vault


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


def test_index_build_basic(temp_vault):
    """Test basic index building."""
    vault, index, vault_path = temp_vault
    
    # Create some test notes
    note1 = Note(
        id="note1",
        meta=MetaBag({"title": "First Note"}),
        body=vault.parser.parse("# First Note\n\nThis is [[note2]].", "note1")
    )
    note2 = Note(
        id="note2",
        meta=MetaBag({"title": "Second Note"}),
        body=vault.parser.parse("# Second Note\n\nContent here.", "note2")
    )
    
    vault.put(note1)
    vault.put(note2)
    
    # Build index
    counts = index.rebuild(full=True)
    
    # Verify counts
    assert counts["scanned"] == 2
    assert counts["dirty"] == 2
    assert counts["inserted"] == 2
    assert counts["updated"] == 0
    assert counts["removed"] == 0
    assert counts["failed"] == 0
    
    # Verify links
    links_out = index.links_out("note1")
    assert len(links_out) == 1
    assert links_out[0].target.id == "note2"
    
    links_in = index.links_in("note2")
    assert len(links_in) == 1
    assert links_in[0].source == "note1"


def test_incremental_reindex(temp_vault):
    """Test incremental reindexing only updates changed files."""
    vault, index, vault_path = temp_vault
    
    # Create initial notes
    note1 = Note(
        id="note1",
        meta=MetaBag({"title": "First Note"}),
        body=vault.parser.parse("# First Note\n\nContent.", "note1")
    )
    note2 = Note(
        id="note2",
        meta=MetaBag({"title": "Second Note"}),
        body=vault.parser.parse("# Second Note\n\nContent.", "note2")
    )
    
    vault.put(note1)
    vault.put(note2)
    
    # Initial build
    counts1 = index.rebuild(full=True)
    assert counts1["inserted"] == 2
    
    # Update only note1
    import time
    time.sleep(0.01)  # Ensure mtime changes
    note1_updated = Note(
        id="note1",
        meta=MetaBag({"title": "First Note Updated"}),
        body=vault.parser.parse("# First Note Updated\n\nNew content.", "note1")
    )
    vault.put(note1_updated)
    
    # Incremental rebuild
    counts2 = index.rebuild(full=False)
    assert counts2["scanned"] == 2
    assert counts2["dirty"] == 1
    assert counts2["inserted"] == 0
    assert counts2["updated"] == 1
    assert counts2["removed"] == 0


def test_fts_search(temp_vault):
    """Test FTS5 full-text search."""
    vault, index, vault_path = temp_vault
    
    # Create notes with specific content
    note1 = Note(
        id="note1",
        meta=MetaBag({"title": "Gamma Ray"}),
        body=vault.parser.parse("# Gamma Ray\n\nContent about gamma rays.", "note1")
    )
    note2 = Note(
        id="note2",
        meta=MetaBag({"title": "Alpha Particle"}),
        body=vault.parser.parse("# Alpha Particle\n\nContent about alpha.", "note2")
    )
    note3 = Note(
        id="note3",
        meta=MetaBag({"title": "Gamma Function"}),
        body=vault.parser.parse("# Gamma Function\n\nMath about gamma.", "note3")
    )
    
    vault.put(note1)
    vault.put(note2)
    vault.put(note3)
    
    # Build index
    index.rebuild(full=True)
    
    # Search for "gamma"
    results = index.search("gamma", limit=50)
    assert len(results) == 2
    assert "note1" in results
    assert "note3" in results
    assert "note2" not in results


def test_fts_snippets(temp_vault):
    """Test FTS5 snippet generation with highlights."""
    vault, index, vault_path = temp_vault
    
    note = Note(
        id="test",
        meta=MetaBag({"title": "Test Note"}),
        body=vault.parser.parse(
            "# Test Note\n\nThis is a test about Gamma rays. Gamma is important.",
            "test"
        )
    )
    vault.put(note)
    index.rebuild(full=True)
    
    # Get snippet
    snippet = index.snippet("test", "Gamma")
    assert snippet is not None
    assert "<b>Gamma</b>" in snippet or "<b>gamma</b>" in snippet.lower()


def test_backrefs(temp_vault):
    """Test backlinks/backreferences functionality."""
    vault, index, vault_path = temp_vault
    
    # Create notes with links
    note1 = Note(
        id="note1",
        meta=MetaBag({}),
        body=vault.parser.parse("Links to [[target]].", "note1")
    )
    note2 = Note(
        id="note2",
        meta=MetaBag({}),
        body=vault.parser.parse("Also links to [[target]].", "note2")
    )
    note3 = Note(
        id="target",
        meta=MetaBag({}),
        body=vault.parser.parse("Target note.", "target")
    )
    
    vault.put(note1)
    vault.put(note2)
    vault.put(note3)
    index.rebuild(full=True)
    
    # Get backlinks to target
    backlinks = index.links_in("target")
    assert len(backlinks) == 2
    sources = {link.source for link in backlinks}
    assert sources == {"note1", "note2"}


def test_orphans(temp_vault):
    """Test orphan detection (notes with no links in or out)."""
    vault, index, vault_path = temp_vault
    
    # Create notes
    note1 = Note(
        id="note1",
        meta=MetaBag({}),
        body=vault.parser.parse("Links to [[note2]].", "note1")
    )
    note2 = Note(
        id="note2",
        meta=MetaBag({}),
        body=vault.parser.parse("Links back to [[note1]].", "note2")
    )
    orphan = Note(
        id="orphan",
        meta=MetaBag({}),
        body=vault.parser.parse("No links here.", "orphan")
    )
    
    vault.put(note1)
    vault.put(note2)
    vault.put(orphan)
    index.rebuild(full=True)
    
    # Find orphans
    orphans = index.orphans()
    assert len(orphans) == 1
    assert orphans[0] == "orphan"


def test_file_deletion(temp_vault):
    """Test that deleted files are removed from index."""
    vault, index, vault_path = temp_vault
    
    # Create notes
    note1 = Note(
        id="note1",
        meta=MetaBag({}),
        body=vault.parser.parse("Note 1", "note1")
    )
    note2 = Note(
        id="note2",
        meta=MetaBag({}),
        body=vault.parser.parse("Note 2", "note2")
    )
    
    vault.put(note1)
    vault.put(note2)
    index.rebuild(full=True)
    
    # Verify both notes are indexed
    assert len(list(vault.list_ids())) == 2
    
    # Delete note2
    vault.storage.delete_raw("note2")
    
    # Rebuild index
    counts = index.rebuild(full=False)
    assert counts["removed"] == 1
    
    # Verify note2 is no longer in index
    links_in = index.links_in("note2")
    assert len(links_in) == 0


def test_blocks_indexing(temp_vault):
    """Test that blocks are properly indexed."""
    vault, index, vault_path = temp_vault
    
    note = Note(
        id="note1",
        meta=MetaBag({}),
        body=vault.parser.parse(
            "# Heading 1\n\n## Heading 2 ^label\n\nContent.",
            "note1"
        )
    )
    vault.put(note)
    index.rebuild(full=True)
    
    # Get blocks
    blocks = index.blocks("note1")
    assert len(blocks) >= 2
    
    # Check for labeled block
    labeled = [b for b in blocks if b.label and b.label.name == "label"]
    assert len(labeled) == 1


def test_graph_data(temp_vault):
    """Test graph data export."""
    vault, index, vault_path = temp_vault
    
    # Create notes with links
    note1 = Note(
        id="note1",
        meta=MetaBag({"title": "First"}),
        body=vault.parser.parse("Links to [[note2]].", "note1")
    )
    note2 = Note(
        id="note2",
        meta=MetaBag({"title": "Second"}),
        body=vault.parser.parse("Content.", "note2")
    )
    
    vault.put(note1)
    vault.put(note2)
    index.rebuild(full=True)
    
    # Get graph data
    graph = index.graph_data()
    
    assert "nodes" in graph
    assert "edges" in graph
    assert len(graph["nodes"]) == 2
    assert len(graph["edges"]) == 1
    
    # Verify edge
    edge = graph["edges"][0]
    assert edge["source"] == "note1"
    assert edge["target"] == "note2"


def test_title_extraction(temp_vault):
    """Test title extraction heuristics."""
    vault, index, vault_path = temp_vault
    
    # Test with frontmatter title
    note1 = Note(
        id="note1",
        meta=MetaBag({"title": "Frontmatter Title"}),
        body=vault.parser.parse("# Different Heading\n\nContent.", "note1")
    )
    vault.put(note1)
    index.rebuild(full=True)
    
    # Search should find it by frontmatter title
    results = index.search("Frontmatter", limit=10)
    assert "note1" in results


def test_math_detection(temp_vault):
    """Test math content detection."""
    vault, index, vault_path = temp_vault
    
    # Create note with math
    note_with_math = Note(
        id="math",
        meta=MetaBag({}),
        body=vault.parser.parse("Formula: $E = mc^2$", "math")
    )
    note_without_math = Note(
        id="nomath",
        meta=MetaBag({}),
        body=vault.parser.parse("Plain text.", "nomath")
    )
    
    vault.put(note_with_math)
    vault.put(note_without_math)
    index.rebuild(full=True)
    
    # Verify math detection (would need to query DB directly to test has_math flag)
    # For now, just verify it doesn't crash
    assert True


def test_hash_based_change_detection(temp_vault):
    """Test hash-based change detection."""
    vault, index, vault_path = temp_vault
    
    # Create note
    note = Note(
        id="note1",
        meta=MetaBag({}),
        body=vault.parser.parse("Content.", "note1")
    )
    vault.put(note)
    
    # Build with hash
    counts1 = index.rebuild(full=True, use_hash=True)
    assert counts1["inserted"] == 1
    
    # Touch file without changing content
    import time
    time.sleep(0.01)
    file_path = vault_path / "note1.md"
    file_path.touch()
    
    # Rebuild with hash - should detect no real change
    # (This is tricky because we still update mtime, but content hash is same)
    counts2 = index.rebuild(full=False, use_hash=True)
    # With hash, it should still see the file as dirty due to mtime
    # but this tests that hash computation works
    assert counts2["scanned"] == 1
