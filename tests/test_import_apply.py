"""Tests for import apply functionality."""


import pytest
import yaml

from hypomnemata.import_migrate.apply import (
    apply_import,
    inject_frontmatter,
    load_manifest,
    save_manifest,
)
from hypomnemata.import_migrate.models import ImportItem, ImportPlan


def test_inject_frontmatter_new_file():
    """Test injecting frontmatter into file without frontmatter."""
    content = "# My Note\n\nSome content here."
    
    result = inject_frontmatter(
        content,
        note_id="abc123",
        title="My Note",
        aliases=["MN", "Note1"]
    )
    
    # Should have frontmatter
    assert result.startswith("---\n")
    assert "id: abc123" in result
    assert "core/title: My Note" in result
    assert "core/aliases:" in result
    assert "- MN" in result
    assert "- Note1" in result
    # Original content preserved
    assert "# My Note" in result
    assert "Some content here." in result


def test_inject_frontmatter_existing():
    """Test updating existing frontmatter."""
    content = """---
existing_key: existing_value
---

# Content"""
    
    result = inject_frontmatter(
        content,
        note_id="xyz789",
        title="Updated Title",
    )
    
    # Parse frontmatter
    lines = result.split('\n')
    assert lines[0] == "---"
    end_idx = lines[1:].index("---") + 1
    fm_text = '\n'.join(lines[1:end_idx])
    fm = yaml.safe_load(fm_text)
    
    assert fm["id"] == "xyz789"
    assert fm["core/title"] == "Updated Title"
    assert fm["existing_key"] == "existing_value"  # Preserved


def test_apply_import_basic(tmp_path):
    """Test basic import application."""
    src_dir = tmp_path / "source"
    src_dir.mkdir()
    dst_vault = tmp_path / "vault"
    
    # Create source file
    src_file = src_dir / "note1.md"
    src_file.write_text("# Test Note\n\nContent here.")
    
    # Create plan
    plan = ImportPlan(
        src=str(src_dir),
        items=[
            ImportItem(
                src="note1.md",
                id="abc123",
                title="Test Note",
                aliases=["TN"],
                status="ok"
            )
        ]
    )
    
    # Apply import
    manifest = apply_import(plan, dst_vault, operation="copy")
    
    # Check destination file exists
    dst_file = dst_vault / "abc123.md"
    assert dst_file.exists()
    
    # Check content
    content = dst_file.read_text()
    assert "id: abc123" in content
    assert "core/title: Test Note" in content
    assert "# Test Note" in content
    
    # Check manifest
    assert len(manifest.entries) == 1
    assert manifest.entries[0].action == "copy"
    assert manifest.entries[0].dst == str(dst_file)


def test_apply_import_move(tmp_path):
    """Test import with move operation."""
    src_dir = tmp_path / "source"
    src_dir.mkdir()
    dst_vault = tmp_path / "vault"
    
    # Create source file
    src_file = src_dir / "note1.md"
    src_file.write_text("# Test Note\n\nContent.")
    
    plan = ImportPlan(
        src=str(src_dir),
        items=[
            ImportItem(
                src="note1.md",
                id="xyz456",
                title="Test Note",
                status="ok"
            )
        ]
    )
    
    # Apply with move
    apply_import(plan, dst_vault, operation="move")
    
    # Source should be gone
    assert not src_file.exists()
    
    # Destination should exist
    dst_file = dst_vault / "xyz456.md"
    assert dst_file.exists()


def test_apply_import_skip_conflicts(tmp_path):
    """Test skipping items with conflict status."""
    src_dir = tmp_path / "source"
    src_dir.mkdir()
    dst_vault = tmp_path / "vault"
    
    # Create source files
    (src_dir / "note1.md").write_text("Content 1")
    (src_dir / "note2.md").write_text("Content 2")
    
    plan = ImportPlan(
        src=str(src_dir),
        items=[
            ImportItem(
                src="note1.md",
                id="id1",
                title="Note 1",
                status="ok"
            ),
            ImportItem(
                src="note2.md",
                id="id2",
                title="Note 2",
                status="conflict",
                reason="Duplicate title"
            ),
        ]
    )
    
    manifest = apply_import(plan, dst_vault)
    
    # Only one file should be imported
    assert len(manifest.entries) == 1
    assert (dst_vault / "id1.md").exists()
    assert not (dst_vault / "id2.md").exists()


def test_apply_import_dry_run(tmp_path):
    """Test dry-run mode."""
    src_dir = tmp_path / "source"
    src_dir.mkdir()
    dst_vault = tmp_path / "vault"
    
    (src_dir / "note1.md").write_text("Content")
    
    plan = ImportPlan(
        src=str(src_dir),
        items=[
            ImportItem(
                src="note1.md",
                id="test123",
                title="Test",
                status="ok"
            )
        ]
    )
    
    # Apply with dry-run
    manifest = apply_import(plan, dst_vault, dry_run=True)
    
    # Nothing should be written
    assert not (dst_vault / "test123.md").exists()
    assert len(manifest.entries) == 0


def test_apply_import_on_conflict_fail(tmp_path):
    """Test failing when destination exists."""
    src_dir = tmp_path / "source"
    src_dir.mkdir()
    dst_vault = tmp_path / "vault"
    dst_vault.mkdir()
    
    # Create source and existing destination
    (src_dir / "note1.md").write_text("New content")
    (dst_vault / "abc123.md").write_text("Existing content")
    
    plan = ImportPlan(
        src=str(src_dir),
        items=[
            ImportItem(
                src="note1.md",
                id="abc123",
                title="Test",
                status="ok"
            )
        ]
    )
    
    # Should raise error
    with pytest.raises(FileExistsError):
        apply_import(plan, dst_vault, on_conflict="fail")


def test_apply_import_on_conflict_skip(tmp_path):
    """Test skipping when destination exists."""
    src_dir = tmp_path / "source"
    src_dir.mkdir()
    dst_vault = tmp_path / "vault"
    dst_vault.mkdir()
    
    (src_dir / "note1.md").write_text("New content")
    (dst_vault / "abc123.md").write_text("Existing content")
    
    plan = ImportPlan(
        src=str(src_dir),
        items=[
            ImportItem(
                src="note1.md",
                id="abc123",
                title="Test",
                status="ok"
            )
        ]
    )
    
    manifest = apply_import(plan, dst_vault, on_conflict="skip")
    
    # Nothing imported
    assert len(manifest.entries) == 0
    # Original file unchanged
    assert (dst_vault / "abc123.md").read_text() == "Existing content"


def test_apply_import_on_conflict_new_id(tmp_path):
    """Test generating new ID when destination exists."""
    src_dir = tmp_path / "source"
    src_dir.mkdir()
    dst_vault = tmp_path / "vault"
    dst_vault.mkdir()
    
    (src_dir / "note1.md").write_text("New content")
    (dst_vault / "abc123.md").write_text("Existing content")
    
    plan = ImportPlan(
        src=str(src_dir),
        items=[
            ImportItem(
                src="note1.md",
                id="abc123",
                title="Test",
                status="ok"
            )
        ]
    )
    
    manifest = apply_import(plan, dst_vault, on_conflict="new-id")
    
    # Should create with different ID
    assert len(manifest.entries) == 1
    # New file created with suffix
    assert (dst_vault / "abc123_1.md").exists()


def test_save_and_load_manifest(tmp_path):
    """Test saving and loading manifest."""
    from hypomnemata.import_migrate.models import ImportManifest, ManifestEntry
    
    manifest = ImportManifest(
        src_dir="/source",
        dst_vault="/vault",
        operation="copy",
        entries=[
            ManifestEntry(
                action="copy",
                src="/source/note1.md",
                dst="/vault/abc123.md",
            )
        ]
    )
    
    # Save
    manifest_path = tmp_path / "manifest.json"
    save_manifest(manifest, manifest_path)
    
    assert manifest_path.exists()
    
    # Load
    loaded = load_manifest(manifest_path)
    
    assert loaded.src_dir == manifest.src_dir
    assert loaded.dst_vault == manifest.dst_vault
    assert len(loaded.entries) == 1
    assert loaded.entries[0].action == "copy"
