"""Tests for heading slicing functionality."""

from hypomnemata.adapters.markdown_parser import MarkdownParser
from hypomnemata.core.model import Note
from hypomnemata.core.slicer import find_heading_by_slug, slice_heading


def test_find_heading_by_slug():
    """Test finding headings by slug."""
    text = """# Main Title

Some content.

## Sub Section

More content.

## Another-Section

Final content.
"""
    parser = MarkdownParser()
    body = parser.parse(text, "test")
    note = Note(id="test", meta={}, body=body)
    
    # Test finding by slug
    block = find_heading_by_slug(note, "main-title")
    assert block is not None
    assert block.heading_text == "Main Title"
    
    block = find_heading_by_slug(note, "sub-section")
    assert block is not None
    assert block.heading_text == "Sub Section"
    
    block = find_heading_by_slug(note, "another-section")
    assert block is not None
    assert block.heading_text == "Another-Section"
    
    # Test non-existent slug
    block = find_heading_by_slug(note, "nonexistent")
    assert block is None


def test_slice_heading_to_next_same_level():
    """Test slicing heading to next heading of same level."""
    text = """# First

Content of first.

# Second

Content of second.
"""
    parser = MarkdownParser()
    body = parser.parse(text, "test")
    note = Note(id="test", meta={}, body=body)
    
    block = find_heading_by_slug(note, "first")
    assert block is not None
    
    start, end = slice_heading(note, block)
    sliced = text[start:end]
    
    assert sliced == """# First

Content of first.

"""


def test_slice_heading_to_higher_level():
    """Test slicing heading to next heading of higher level."""
    text = """# Main

Content.

## Sub Section

Sub content.

# Next Main

More content.
"""
    parser = MarkdownParser()
    body = parser.parse(text, "test")
    note = Note(id="test", meta={}, body=body)
    
    block = find_heading_by_slug(note, "sub-section")
    assert block is not None
    
    start, end = slice_heading(note, block)
    sliced = text[start:end]
    
    assert sliced == """## Sub Section

Sub content.

"""


def test_slice_heading_to_eof():
    """Test slicing heading to end of file."""
    text = """# First

Content.

## Sub Section

Sub content until end.
"""
    parser = MarkdownParser()
    body = parser.parse(text, "test")
    note = Note(id="test", meta={}, body=body)
    
    block = find_heading_by_slug(note, "sub-section")
    assert block is not None
    
    start, end = slice_heading(note, block)
    sliced = text[start:end]
    
    assert sliced == """## Sub Section

Sub content until end.
"""


def test_slice_nested_headings():
    """Test slicing with multiple heading levels."""
    text = """# Level 1

Content.

## Level 2

L2 content.

### Level 3

L3 content.

## Another Level 2

More L2 content.

# Another Level 1

Final content.
"""
    parser = MarkdownParser()
    body = parser.parse(text, "test")
    note = Note(id="test", meta={}, body=body)
    
    # Slice level 2 should include level 3 but stop at next level 2
    block = find_heading_by_slug(note, "level-2")
    assert block is not None
    
    start, end = slice_heading(note, block)
    sliced = text[start:end]
    
    expected = """## Level 2

L2 content.

### Level 3

L3 content.

"""
    assert sliced == expected
