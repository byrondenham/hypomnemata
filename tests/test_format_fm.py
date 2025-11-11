"""Tests for frontmatter normalization."""

import pytest

from hypomnemata.format.fm import normalize_frontmatter


def test_normalize_frontmatter_adds_missing_id():
    """Test that missing ID is added."""
    text = "---\ncore/title: Test Note\n---\n\nContent here"
    result = normalize_frontmatter(text, "abc123")
    
    assert "id: abc123" in result
    assert "core/title: Test Note" in result


def test_normalize_frontmatter_fixes_wrong_id():
    """Test that incorrect ID is corrected."""
    text = "---\nid: wrong123\ncore/title: Test Note\n---\n\nContent here"
    result = normalize_frontmatter(text, "correct123")
    
    assert "id: correct123" in result
    assert "id: wrong123" not in result


def test_normalize_frontmatter_ordering():
    """Test that keys are ordered correctly."""
    text = """---
user/tag: important
core/aliases:
  - Test
id: abc123
core/title: Test Note
---

Content here"""
    
    result = normalize_frontmatter(text, "abc123")
    
    # Split into lines and find key positions
    lines = result.split('\n')
    
    # Find positions of keys
    id_pos = next(i for i, line in enumerate(lines) if line.startswith('id:'))
    title_pos = next(i for i, line in enumerate(lines) if line.startswith('core/title:'))
    aliases_pos = next(i for i, line in enumerate(lines) if line.startswith('core/aliases:'))
    
    # id should come before core/title, which should come before core/aliases
    assert id_pos < title_pos < aliases_pos


def test_normalize_frontmatter_no_metadata():
    """Test handling of notes without frontmatter."""
    text = "# Just a heading\n\nSome content"
    result = normalize_frontmatter(text, "abc123")
    
    # Should add frontmatter with just the id
    assert "---\nid: abc123\n---" in result
    assert "# Just a heading" in result


def test_normalize_frontmatter_preserves_content():
    """Test that body content is preserved."""
    text = "---\nid: abc123\n---\n\n# Heading\n\nSome **bold** text with [[links]]"
    result = normalize_frontmatter(text, "abc123")
    
    assert "# Heading" in result
    assert "Some **bold** text with [[links]]" in result


def test_normalize_frontmatter_single_blank_line():
    """Test that exactly one blank line separates frontmatter from body."""
    text = "---\nid: abc123\n---\n\n\n\n# Heading"
    result = normalize_frontmatter(text, "abc123")
    
    # Should have exactly one blank line after ---
    assert "---\n\n# Heading" in result
