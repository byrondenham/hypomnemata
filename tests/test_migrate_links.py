"""Tests for link migration functionality."""

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
from hypomnemata.import_migrate.migrate import migrate_wiki_links, resolve_target


@pytest.fixture
def temp_vault():
    """Create a temporary vault with index for testing."""
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


def test_resolve_target_by_title(temp_vault):
    """Test resolving a target by exact title match."""
    vault, index, vault_path = temp_vault
    
    # Create a note with a title
    note = Note(
        id="abc123",
        meta=MetaBag({"core/title": "My Test Note"}),
        body=vault.parser.parse("# My Test Note\n\nContent", "abc123")
    )
    vault.put(note)
    index.rebuild()
    
    # Resolve by title
    result = resolve_target("My Test Note", index, resolver_mode="both")
    
    assert result == "abc123"


def test_resolve_target_by_alias(temp_vault):
    """Test resolving a target by exact alias match."""
    vault, index, vault_path = temp_vault
    
    # Create a note with aliases (stored as core/aliases list)
    note = Note(
        id="xyz789",
        meta=MetaBag({
            "core/title": "Full Title",
            "core/aliases": ["QR", "Quick Ref"]  # List of aliases
        }),
        body=vault.parser.parse("Content", "xyz789")
    )
    vault.put(note)
    index.rebuild()
    
    # Resolve by alias
    result = resolve_target("QR", index, resolver_mode="both")
    
    assert result == "xyz789"


def test_resolve_target_not_found(temp_vault):
    """Test that non-existent targets return None."""
    vault, index, vault_path = temp_vault
    
    # Don't create any notes
    index.rebuild()
    
    result = resolve_target("Non Existent", index, resolver_mode="both")
    
    assert result is None


def test_migrate_wiki_links_simple(temp_vault):
    """Test migrating simple wiki links."""
    vault, index, vault_path = temp_vault
    
    # Create target note
    note = Note(
        id="target123",
        meta=MetaBag({"core/title": "Target Note"}),
        body=vault.parser.parse("Content", "target123")
    )
    vault.put(note)
    index.rebuild()
    
    # Content with wiki link
    content = "This is a link to [[Target Note]]."
    
    migrated, errors = migrate_wiki_links(content, index)
    
    assert "[[target123]]" in migrated
    assert "[[Target Note]]" not in migrated
    assert len(errors) == 0


def test_migrate_wiki_links_with_display_text(temp_vault):
    """Test migrating wiki links with display text."""
    vault, index, vault_path = temp_vault
    
    # Create target note
    note = Note(
        id="note456",
        meta=MetaBag({"core/title": "Long Title"}),
        body=vault.parser.parse("Content", "note456")
    )
    vault.put(note)
    index.rebuild()
    
    content = "Link: [[Long Title|Short]]."
    
    migrated, errors = migrate_wiki_links(content, index)
    
    assert "[[note456|Short]]" in migrated
    assert len(errors) == 0


def test_migrate_wiki_links_with_anchor(temp_vault):
    """Test migrating wiki links with anchors."""
    vault, index, vault_path = temp_vault
    
    # Create target note
    note = Note(
        id="note789",
        meta=MetaBag({"core/title": "Note With Sections"}),
        body=vault.parser.parse("# Heading\nContent", "note789")
    )
    vault.put(note)
    index.rebuild()
    
    content = "Link: [[Note With Sections#heading]]."
    
    migrated, errors = migrate_wiki_links(content, index)
    
    assert "[[note789#heading]]" in migrated
    assert len(errors) == 0


def test_migrate_wiki_links_transclusion(temp_vault):
    """Test migrating transclusion links."""
    vault, index, vault_path = temp_vault
    
    # Create target note
    note = Note(
        id="embed123",
        meta=MetaBag({"core/title": "Embedded Note"}),
        body=vault.parser.parse("Content to embed", "embed123")
    )
    vault.put(note)
    index.rebuild()
    
    content = "Embed: ![[Embedded Note]]"
    
    migrated, errors = migrate_wiki_links(content, index)
    
    assert "![[embed123]]" in migrated
    assert len(errors) == 0


def test_migrate_wiki_links_unresolvable(temp_vault):
    """Test that unresolvable links are kept and reported as errors."""
    vault, index, vault_path = temp_vault
    
    # Don't create the target note
    index.rebuild()
    
    content = "Link to [[Non Existent Note]]."
    
    migrated, errors = migrate_wiki_links(content, index)
    
    # Link should be unchanged
    assert "[[Non Existent Note]]" in migrated
    assert len(errors) == 1
    assert "Non Existent Note" in errors[0]


def test_migrate_wiki_links_multiple(temp_vault):
    """Test migrating multiple wiki links."""
    vault, index, vault_path = temp_vault
    
    # Create multiple target notes
    note1 = Note(
        id="id1",
        meta=MetaBag({"core/title": "First"}),
        body=vault.parser.parse("Content", "id1")
    )
    note2 = Note(
        id="id2",
        meta=MetaBag({"core/title": "Second"}),
        body=vault.parser.parse("Content", "id2")
    )
    vault.put(note1)
    vault.put(note2)
    index.rebuild()
    
    content = "Links: [[First]] and [[Second]]."
    
    migrated, errors = migrate_wiki_links(content, index)
    
    assert "[[id1]]" in migrated
    assert "[[id2]]" in migrated
    assert "[[First]]" not in migrated
    assert "[[Second]]" not in migrated
    assert len(errors) == 0


def test_migrate_wiki_links_prefer_alias(temp_vault):
    """Test preferring alias over title when both match."""
    vault, index, vault_path = temp_vault
    
    # Create two notes: one with title match, one with alias match
    note1 = Note(
        id="title_id",
        meta=MetaBag({"core/title": "Match"}),
        body=vault.parser.parse("Content", "title_id")
    )
    note2 = Note(
        id="alias_id",
        meta=MetaBag({
            "core/title": "Other",
            "core/aliases": ["Match"]  # Alias list
        }),
        body=vault.parser.parse("Content", "alias_id")
    )
    vault.put(note1)
    vault.put(note2)
    index.rebuild()
    
    content = "Link: [[Match]]"
    
    # Prefer alias
    migrated, errors = migrate_wiki_links(content, index, prefer="alias")
    
    assert "[[alias_id]]" in migrated
    assert len(errors) == 0


def test_migrate_wiki_links_prefer_title(temp_vault):
    """Test preferring title over alias when both match."""
    vault, index, vault_path = temp_vault
    
    # Create two notes: one with title match, one with alias match
    note1 = Note(
        id="title_id",
        meta=MetaBag({"core/title": "Match"}),
        body=vault.parser.parse("Content", "title_id")
    )
    note2 = Note(
        id="alias_id",
        meta=MetaBag({
            "core/title": "Other",
            "core/aliases": ["Match"]  # Alias list
        }),
        body=vault.parser.parse("Content", "alias_id")
    )
    vault.put(note1)
    vault.put(note2)
    index.rebuild()
    
    content = "Link: [[Match]]"
    
    # Prefer title
    migrated, errors = migrate_wiki_links(content, index, prefer="title")
    
    assert "[[title_id]]" in migrated
    assert len(errors) == 0
