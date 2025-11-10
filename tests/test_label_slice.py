"""Tests for label-based slicing functionality."""

from hypomnemata.adapters.markdown_parser import MarkdownParser
from hypomnemata.core.model import Note
from hypomnemata.core.slicer import find_label, slice_block


def test_find_label_on_heading():
    """Test finding labels attached to headings."""
    text = """# Main Title

Some content.

## Subsection ^myblock

Labeled content.
"""
    parser = MarkdownParser()
    body = parser.parse(text, "test")
    note = Note(id="test", meta={}, body=body)
    
    block = find_label(note, "myblock")
    assert block is not None
    assert block.kind == "heading"
    assert block.heading_text == "Subsection ^myblock"


def test_find_label_on_fence():
    """Test finding labels attached to fenced blocks."""
    text = """# Title

Some text.

```python ^code
def hello():
    print("world")
```

More text.
"""
    parser = MarkdownParser()
    body = parser.parse(text, "test")
    note = Note(id="test", meta={}, body=body)
    
    block = find_label(note, "code")
    assert block is not None
    assert block.kind == "fence"
    assert "^code" in block.fence_info


def test_slice_labeled_fence():
    """Test slicing a labeled fenced block returns exact fence range."""
    text = """# Title

Before fence.

```python ^code
def hello():
    print("world")
```

After fence.
"""
    parser = MarkdownParser()
    body = parser.parse(text, "test")
    note = Note(id="test", meta={}, body=body)
    
    block = find_label(note, "code")
    assert block is not None
    
    start, end = slice_block(note, block)
    sliced = text[start:end]
    
    expected = """```python ^code
def hello():
    print("world")
```
"""
    assert sliced == expected


def test_slice_labeled_heading():
    """Test slicing a labeled heading uses heading slice rules."""
    text = """# Title

Content.

## Section ^label

Section content.

## Next Section

More content.
"""
    parser = MarkdownParser()
    body = parser.parse(text, "test")
    note = Note(id="test", meta={}, body=body)
    
    block = find_label(note, "label")
    assert block is not None
    
    start, end = slice_block(note, block)
    sliced = text[start:end]
    
    expected = """## Section ^label

Section content.

"""
    assert sliced == expected


def test_multiple_labels():
    """Test handling multiple labels in a note."""
    text = """# Title

```python ^code1
print("first")
```

Some text.

```python ^code2
print("second")
```

## Section ^heading1

Content.
"""
    parser = MarkdownParser()
    body = parser.parse(text, "test")
    note = Note(id="test", meta={}, body=body)
    
    # Should find first occurrence
    block1 = find_label(note, "code1")
    assert block1 is not None
    assert "code1" in block1.fence_info
    
    block2 = find_label(note, "code2")
    assert block2 is not None
    assert "code2" in block2.fence_info
    
    block3 = find_label(note, "heading1")
    assert block3 is not None
    assert block3.kind == "heading"


def test_fence_label_with_language():
    """Test fence label parsing with language specifier."""
    text = """```latex ^equation
\\int_0^\\infty e^{-x^2} dx
```
"""
    parser = MarkdownParser()
    body = parser.parse(text, "test")
    note = Note(id="test", meta={}, body=body)
    
    block = find_label(note, "equation")
    assert block is not None
    assert block.kind == "fence"
    assert "latex" in block.fence_info
    assert "^equation" in block.fence_info


def test_no_label_found():
    """Test that None is returned when label doesn't exist."""
    text = """# Title

No labels here.
"""
    parser = MarkdownParser()
    body = parser.parse(text, "test")
    note = Note(id="test", meta={}, body=body)
    
    block = find_label(note, "nonexistent")
    assert block is None
