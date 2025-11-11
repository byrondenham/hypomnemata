"""Tests for import plan functionality."""



from hypomnemata.import_migrate.plan import (
    build_import_plan,
    extract_metadata,
    load_plan_json,
    save_plan_csv,
    save_plan_json,
)


def test_extract_metadata_from_frontmatter(tmp_path):
    """Test extracting title and aliases from YAML frontmatter."""
    file_path = tmp_path / "test.md"
    content = """---
core/title: My Test Note
core/aliases:
  - Quick Ref
  - QR
---

# Content here
"""
    file_path.write_text(content)
    
    title, aliases = extract_metadata(file_path)
    
    assert title == "My Test Note"
    assert aliases == ["Quick Ref", "QR"]


def test_extract_metadata_from_heading(tmp_path):
    """Test extracting title from first H1 heading."""
    file_path = tmp_path / "test.md"
    content = """# My Heading Title

Some content here.
"""
    file_path.write_text(content)
    
    title, aliases = extract_metadata(file_path)
    
    assert title == "My Heading Title"
    assert aliases == []


def test_extract_metadata_fallback_to_filename(tmp_path):
    """Test fallback to filename when no title found."""
    file_path = tmp_path / "my-filename.md"
    content = "Just some content without heading or frontmatter."
    file_path.write_text(content)
    
    title, aliases = extract_metadata(file_path)
    
    assert title == "my-filename"
    assert aliases == []


def test_build_import_plan_basic(tmp_path):
    """Test basic import plan generation."""
    src_dir = tmp_path / "source"
    src_dir.mkdir()
    
    # Create test files
    (src_dir / "note1.md").write_text("---\ncore/title: First Note\n---\nContent")
    (src_dir / "note2.md").write_text("---\ncore/title: Second Note\n---\nContent")
    
    plan = build_import_plan(src_dir, id_strategy="hash")
    
    assert len(plan.items) == 2
    assert plan.id_strategy == "hash"
    assert all(item.status == "ok" for item in plan.items)
    assert all(item.id for item in plan.items)  # IDs generated


def test_build_import_plan_detects_duplicate_titles(tmp_path):
    """Test that duplicate titles are detected as conflicts."""
    src_dir = tmp_path / "source"
    src_dir.mkdir()
    
    # Create files with duplicate titles
    (src_dir / "note1.md").write_text("---\ncore/title: Same Title\n---\nContent 1")
    (src_dir / "note2.md").write_text("---\ncore/title: Same Title\n---\nContent 2")
    
    plan = build_import_plan(src_dir)
    
    assert len(plan.items) == 2
    # Both should be marked as conflicts
    assert all(item.status == "conflict" for item in plan.items)
    assert "title:Same Title" in plan.conflicts
    assert len(plan.conflicts["title:Same Title"]) == 2


def test_build_import_plan_detects_duplicate_aliases(tmp_path):
    """Test that duplicate aliases are detected as conflicts."""
    src_dir = tmp_path / "source"
    src_dir.mkdir()
    
    # Create files with duplicate aliases
    (src_dir / "note1.md").write_text("---\ncore/title: First\ncore/aliases: [QR]\n---\nContent 1")
    (src_dir / "note2.md").write_text("---\ncore/title: Second\ncore/aliases: [QR]\n---\nContent 2")
    
    plan = build_import_plan(src_dir)
    
    assert len(plan.items) == 2
    assert "alias:QR" in plan.conflicts
    assert len(plan.conflicts["alias:QR"]) == 2


def test_build_import_plan_random_ids_are_unique(tmp_path):
    """Test that random IDs are unique."""
    src_dir = tmp_path / "source"
    src_dir.mkdir()
    
    # Create multiple files
    for i in range(10):
        (src_dir / f"note{i}.md").write_text(f"---\ncore/title: Note {i}\n---\nContent {i}")
    
    plan = build_import_plan(src_dir, id_strategy="random")
    
    # All IDs should be unique
    ids = [item.id for item in plan.items]
    assert len(ids) == len(set(ids))


def test_build_import_plan_hash_ids_are_deterministic(tmp_path):
    """Test that hash IDs are deterministic based on path."""
    src_dir = tmp_path / "source"
    src_dir.mkdir()
    
    (src_dir / "note1.md").write_text("---\ncore/title: Test\n---\nContent")
    
    plan1 = build_import_plan(src_dir, id_strategy="hash")
    plan2 = build_import_plan(src_dir, id_strategy="hash")
    
    assert plan1.items[0].id == plan2.items[0].id


def test_save_and_load_plan_json(tmp_path):
    """Test saving and loading plan JSON."""
    src_dir = tmp_path / "source"
    src_dir.mkdir()
    
    (src_dir / "note1.md").write_text("---\ncore/title: Test Note\n---\nContent")
    
    plan = build_import_plan(src_dir)
    
    # Save to JSON
    json_path = tmp_path / "plan.json"
    save_plan_json(plan, json_path)
    
    assert json_path.exists()
    
    # Load back
    loaded_plan = load_plan_json(json_path)
    
    assert len(loaded_plan.items) == len(plan.items)
    assert loaded_plan.items[0].id == plan.items[0].id
    assert loaded_plan.items[0].title == plan.items[0].title


def test_save_plan_csv(tmp_path):
    """Test saving plan to CSV."""
    src_dir = tmp_path / "source"
    src_dir.mkdir()
    
    (src_dir / "note1.md").write_text("---\ncore/title: Test\ncore/aliases: [T1, T2]\n---\nContent")
    
    plan = build_import_plan(src_dir)
    
    # Save to CSV
    csv_path = tmp_path / "plan.csv"
    save_plan_csv(plan, csv_path)
    
    assert csv_path.exists()
    
    # Check CSV content
    content = csv_path.read_text()
    assert "src,id,title,aliases,status,reason" in content
    assert "Test" in content
    assert "T1|T2" in content  # Aliases joined with |
