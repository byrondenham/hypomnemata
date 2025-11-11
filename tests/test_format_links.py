"""Tests for link normalization."""

import pytest

from hypomnemata.format.links import normalize_links


def test_normalize_links_removes_spaces():
    """Test that spaces inside brackets are removed."""
    text = "[[ abc123 | Title ]]"
    result = normalize_links(text)
    assert result == "[[abc123|Title]]"


def test_normalize_links_transclusion():
    """Test transclusion normalization."""
    text = "![[  abc123  ]]"
    result = normalize_links(text)
    assert result == "![[abc123]]"


def test_normalize_links_with_anchor():
    """Test links with anchors."""
    text = "[[ abc123 # heading | Title ]]"
    result = normalize_links(text)
    assert result == "[[abc123#heading|Title]]"


def test_normalize_links_with_block_label():
    """Test links with block labels."""
    text = "![[abc123#^label]]"
    result = normalize_links(text)
    assert result == "![[abc123#^label]]"


def test_normalize_links_ids_only():
    """Test collapsing [[id|id]] to [[id]]."""
    text = "[[abc123|abc123]]"
    result = normalize_links(text, ids_only=True)
    assert result == "[[abc123]]"


def test_normalize_links_ids_only_different():
    """Test that [[id|title]] is preserved when ids_only is True."""
    text = "[[abc123|Different Title]]"
    result = normalize_links(text, ids_only=True)
    assert result == "[[abc123|Different Title]]"


def test_normalize_links_preserves_code_fence():
    """Test that code fences are not processed."""
    text = """```python
[[abc123|Title]]
```"""
    result = normalize_links(text)
    # Should preserve spaces in code
    assert "[[abc123|Title]]" in result


def test_normalize_links_preserves_inline_code():
    """Test that inline code is not processed."""
    text = "Here is `[[abc123|Title]]` in code"
    result = normalize_links(text)
    assert "`[[abc123|Title]]`" in result


def test_normalize_links_multiple():
    """Test multiple links in one text."""
    text = "Link to [[ abc | Title ]] and another ![[  def  ]]"
    result = normalize_links(text)
    assert result == "Link to [[abc|Title]] and another ![[def]]"


def test_normalize_links_with_rel():
    """Test links with rel: prefix."""
    text = "[[rel:parent|abc123|Title]]"
    result = normalize_links(text)
    assert result == "[[rel:parent|abc123|Title]]"


def test_normalize_links_complex():
    """Test complex combination."""
    text = """# Heading

Link to [[ note1 | Note 1 ]] and image ![[  img123  ]].

```python
# This should not be touched
[[  code_example  ]]
```

Another link [[note2#heading|Section]].
"""
    
    result = normalize_links(text)
    
    assert "[[note1|Note 1]]" in result
    assert "![[img123]]" in result
    assert "[[note2#heading|Section]]" in result
    # Code should be preserved
    assert "[[  code_example  ]]" in result
