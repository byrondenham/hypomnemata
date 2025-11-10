"""Tests for hypo yank CLI command."""

import subprocess
import tempfile
from pathlib import Path


def test_yank_whole_note():
    """Test yanking entire note without anchor."""
    with tempfile.TemporaryDirectory() as tmpdir:
        vault = Path(tmpdir)
        note_path = vault / "test1234.md"
        note_path.write_text("""---
id: test1234
---

# Test Note

This is content.
""")
        
        result = subprocess.run(
            ["hypo", "--vault", str(vault), "yank", "test1234"],
            capture_output=True,
            text=True,
        )
        
        assert result.returncode == 0
        assert "# Test Note" in result.stdout
        assert "This is content." in result.stdout
        # Frontmatter should be stripped
        assert "---" not in result.stdout
        assert "id: test1234" not in result.stdout


def test_yank_block_label():
    """Test yanking with block label anchor."""
    with tempfile.TemporaryDirectory() as tmpdir:
        vault = Path(tmpdir)
        note_path = vault / "test1234.md"
        note_path.write_text("""---
id: test1234
---

# Test

```python ^code
def hello():
    print("world")
```

More text.
""")
        
        result = subprocess.run(
            ["hypo", "--vault", str(vault), "yank", "test1234#^code"],
            capture_output=True,
            text=True,
        )
        
        assert result.returncode == 0
        assert "```python ^code" in result.stdout
        assert 'def hello():' in result.stdout
        assert "```" in result.stdout
        # Should not include text after fence
        assert "More text" not in result.stdout


def test_yank_heading_slug():
    """Test yanking with heading slug anchor."""
    with tempfile.TemporaryDirectory() as tmpdir:
        vault = Path(tmpdir)
        note_path = vault / "test1234.md"
        note_path.write_text("""---
id: test1234
---

# Test

## My Section

Section content.

## Another Section

More content.
""")
        
        result = subprocess.run(
            ["hypo", "--vault", str(vault), "yank", "test1234#my-section"],
            capture_output=True,
            text=True,
        )
        
        assert result.returncode == 0
        assert "## My Section" in result.stdout
        assert "Section content." in result.stdout
        # Should stop at next heading of same level
        assert "## Another Section" not in result.stdout


def test_yank_plain_flag():
    """Test yanking with --plain flag to strip fences."""
    with tempfile.TemporaryDirectory() as tmpdir:
        vault = Path(tmpdir)
        note_path = vault / "test1234.md"
        note_path.write_text("""---
id: test1234
---

```python ^code
def hello():
    print("world")
```
""")
        
        result = subprocess.run(
            ["hypo", "--vault", str(vault), "yank", "test1234#^code", "--plain"],
            capture_output=True,
            text=True,
        )
        
        assert result.returncode == 0
        assert 'def hello():' in result.stdout
        assert 'print("world")' in result.stdout
        # Fence markers should be stripped
        assert "```" not in result.stdout


def test_yank_nonexistent_note():
    """Test yanking nonexistent note returns error."""
    with tempfile.TemporaryDirectory() as tmpdir:
        vault = Path(tmpdir)
        
        result = subprocess.run(
            ["hypo", "--vault", str(vault), "yank", "nonexistent"],
            capture_output=True,
            text=True,
        )
        
        assert result.returncode == 1
        assert "not found" in result.stderr


def test_yank_nonexistent_anchor():
    """Test yanking with nonexistent anchor returns error."""
    with tempfile.TemporaryDirectory() as tmpdir:
        vault = Path(tmpdir)
        note_path = vault / "test1234.md"
        note_path.write_text("""---
id: test1234
---

# Test

Content.
""")
        
        result = subprocess.run(
            ["hypo", "--vault", str(vault), "yank", "test1234#^nonexistent"],
            capture_output=True,
            text=True,
        )
        
        assert result.returncode == 1
        assert "not found" in result.stderr


def test_yank_context_flag():
    """Test yanking with --context flag."""
    with tempfile.TemporaryDirectory() as tmpdir:
        vault = Path(tmpdir)
        note_path = vault / "test1234.md"
        note_path.write_text("""---
id: test1234
---

Line 1
Line 2
## Target
Target content
Line after

More lines
""")
        
        result = subprocess.run(
            ["hypo", "--vault", str(vault), "yank", "test1234#target", "--context", "1"],
            capture_output=True,
            text=True,
        )
        
        assert result.returncode == 0
        # Should include 1 line before and after
        assert "Line 2" in result.stdout
        assert "## Target" in result.stdout
        assert "Target content" in result.stdout
        assert "Line after" in result.stdout
