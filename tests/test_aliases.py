"""Tests for alias functionality."""

import tempfile
from pathlib import Path

from hypomnemata.adapters.fs_storage import FsStorage
from hypomnemata.adapters.markdown_parser import MarkdownParser
from hypomnemata.adapters.sqlite_index import SQLiteIndex
from hypomnemata.adapters.yaml_codec import MarkdownNoteCodec, YamlFrontmatter
from hypomnemata.core.vault import Vault


def test_alias_indexing():
    """Test that aliases are indexed correctly."""
    with tempfile.TemporaryDirectory() as tmpdir:
        vault_dir = Path(tmpdir) / "vault"
        vault_dir.mkdir()
        db_dir = Path(tmpdir) / ".hypo"
        db_dir.mkdir()
        db_path = db_dir / "index.sqlite"
        
        # Create a test note with aliases
        note_path = vault_dir / "test123.md"
        note_path.write_text("""---
id: test123
core/title: Test Title
core/aliases:
  - First Alias
  - Second Alias
---

# Test Note
""")
        
        # Create vault and index
        storage = FsStorage(vault_dir)
        parser = MarkdownParser()
        codec = MarkdownNoteCodec(YamlFrontmatter())
        vault = Vault(storage, parser, codec)
        
        index = SQLiteIndex(db_path=db_path, vault_path=vault_dir, vault=vault)
        index._ensure_schema()
        
        # Index the note
        counts = index.rebuild(full=True)
        assert counts['inserted'] == 1
        
        # Check that aliases are in kv table
        conn = index._conn()
        try:
            aliases = conn.execute(
                "SELECT value FROM kv WHERE note_id = ? AND key = 'core/alias' ORDER BY value",
                ("test123",)
            ).fetchall()
            
            assert len(aliases) == 2
            assert aliases[0][0] == "First Alias"
            assert aliases[1][0] == "Second Alias"
        finally:
            conn.close()


def test_alias_search():
    """Test searching by alias."""
    with tempfile.TemporaryDirectory() as tmpdir:
        vault_dir = Path(tmpdir) / "vault"
        vault_dir.mkdir()
        db_dir = Path(tmpdir) / ".hypo"
        db_dir.mkdir()
        db_path = db_dir / "index.sqlite"
        
        # Create test notes
        note1 = vault_dir / "note1.md"
        note1.write_text("""---
id: note1
core/title: Note One
core/aliases:
  - First Note
  - Primary Note
---

Content of note one.
""")
        
        note2 = vault_dir / "note2.md"
        note2.write_text("""---
id: note2
core/title: Note Two
core/aliases:
  - Second Note
---

Content of note two.
""")
        
        # Create vault and index
        storage = FsStorage(vault_dir)
        parser = MarkdownParser()
        codec = MarkdownNoteCodec(YamlFrontmatter())
        vault = Vault(storage, parser, codec)
        
        index = SQLiteIndex(db_path=db_path, vault_path=vault_dir, vault=vault)
        index._ensure_schema()
        index.rebuild(full=True)
        
        # Search for alias
        conn = index._conn()
        try:
            # Exact match
            result = conn.execute(
                "SELECT note_id FROM kv WHERE key = 'core/alias' AND value = ?",
                ("First Note",)
            ).fetchone()
            assert result is not None
            assert result[0] == "note1"
            
            # Partial match
            results = conn.execute(
                "SELECT note_id FROM kv WHERE key = 'core/alias' AND value LIKE ?",
                ("%Note%",)
            ).fetchall()
            assert len(results) == 3  # First Note, Primary Note, Second Note
        finally:
            conn.close()


def test_title_extraction():
    """Test title extraction from core/title metadata."""
    with tempfile.TemporaryDirectory() as tmpdir:
        vault_dir = Path(tmpdir) / "vault"
        vault_dir.mkdir()
        db_dir = Path(tmpdir) / ".hypo"
        db_dir.mkdir()
        db_path = db_dir / "index.sqlite"
        
        # Create a test note with core/title
        note_path = vault_dir / "test123.md"
        note_path.write_text("""---
id: test123
core/title: Custom Title
---

# Heading Title

Content.
""")
        
        # Create vault and index
        storage = FsStorage(vault_dir)
        parser = MarkdownParser()
        codec = MarkdownNoteCodec(YamlFrontmatter())
        vault = Vault(storage, parser, codec)
        
        index = SQLiteIndex(db_path=db_path, vault_path=vault_dir, vault=vault)
        index._ensure_schema()
        index.rebuild(full=True)
        
        # Check that core/title is used as the title
        conn = index._conn()
        try:
            title = conn.execute(
                "SELECT title FROM notes WHERE id = ?",
                ("test123",)
            ).fetchone()
            
            assert title is not None
            assert title[0] == "Custom Title"
        finally:
            conn.close()


def test_title_fallback():
    """Test title extraction fallback to legacy title."""
    with tempfile.TemporaryDirectory() as tmpdir:
        vault_dir = Path(tmpdir) / "vault"
        vault_dir.mkdir()
        db_dir = Path(tmpdir) / ".hypo"
        db_dir.mkdir()
        db_path = db_dir / "index.sqlite"
        
        # Create a test note with legacy title
        note_path = vault_dir / "test123.md"
        note_path.write_text("""---
id: test123
title: Legacy Title
---

# Heading Title

Content.
""")
        
        # Create vault and index
        storage = FsStorage(vault_dir)
        parser = MarkdownParser()
        codec = MarkdownNoteCodec(YamlFrontmatter())
        vault = Vault(storage, parser, codec)
        
        index = SQLiteIndex(db_path=db_path, vault_path=vault_dir, vault=vault)
        index._ensure_schema()
        index.rebuild(full=True)
        
        # Check that legacy title is used
        conn = index._conn()
        try:
            title = conn.execute(
                "SELECT title FROM notes WHERE id = ?",
                ("test123",)
            ).fetchone()
            
            assert title is not None
            assert title[0] == "Legacy Title"
        finally:
            conn.close()
