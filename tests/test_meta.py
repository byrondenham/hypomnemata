"""Tests for metadata CLI commands."""

import tempfile
from pathlib import Path

from hypomnemata.adapters.fs_storage import FsStorage
from hypomnemata.adapters.markdown_parser import MarkdownParser
from hypomnemata.adapters.yaml_codec import MarkdownNoteCodec, YamlFrontmatter
from hypomnemata.core.vault import Vault


def test_meta_set_and_get():
    """Test setting and getting metadata."""
    with tempfile.TemporaryDirectory() as tmpdir:
        vault_dir = Path(tmpdir) / "vault"
        vault_dir.mkdir()
        
        # Create a test note
        note_path = vault_dir / "test123.md"
        note_path.write_text("""---
id: test123
---

# Test Note
""")
        
        # Create vault
        storage = FsStorage(vault_dir)
        parser = MarkdownParser()
        codec = MarkdownNoteCodec(YamlFrontmatter())
        vault = Vault(storage, parser, codec)
        
        # Load note and set metadata
        note = vault.get("test123")
        assert note is not None
        
        note.meta["core/title"] = "My Title"
        note.meta["core/aliases"] = ["alias1", "alias2"]
        note.meta["user/tags"] = ["tag1", "tag2"]
        
        # Save note
        vault.put(note)
        
        # Reload and verify
        note2 = vault.get("test123")
        assert note2 is not None
        assert note2.meta["core/title"] == "My Title"
        assert note2.meta["core/aliases"] == ["alias1", "alias2"]
        assert note2.meta["user/tags"] == ["tag1", "tag2"]


def test_meta_unset():
    """Test removing metadata keys."""
    with tempfile.TemporaryDirectory() as tmpdir:
        vault_dir = Path(tmpdir) / "vault"
        vault_dir.mkdir()
        
        # Create a test note
        note_path = vault_dir / "test123.md"
        note_path.write_text("""---
id: test123
title: Original Title
core/title: Custom Title
---

# Test Note
""")
        
        # Create vault
        storage = FsStorage(vault_dir)
        parser = MarkdownParser()
        codec = MarkdownNoteCodec(YamlFrontmatter())
        vault = Vault(storage, parser, codec)
        
        # Load note and remove metadata
        note = vault.get("test123")
        assert note is not None
        assert "title" in note.meta
        assert "core/title" in note.meta
        
        del note.meta["core/title"]
        vault.put(note)
        
        # Reload and verify
        note2 = vault.get("test123")
        assert note2 is not None
        assert "title" in note2.meta
        assert "core/title" not in note2.meta
