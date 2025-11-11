"""Tests for hypo locate CLI command."""

import json
import subprocess
import tempfile
from pathlib import Path


def test_locate_whole_note():
    """Test locating entire note returns full range and lines."""
    with tempfile.TemporaryDirectory() as tmpdir:
        vault = Path(tmpdir)
        note_path = vault / "test1234.md"
        note_path.write_text("""---
id: test1234
title: Test Note
---

# Test Note

This is content.
More content here.
""")
        
        result = subprocess.run(
            ["hypo", "--vault", str(vault), "locate", "test1234"],
            capture_output=True,
            text=True,
        )
        
        assert result.returncode == 0
        data = json.loads(result.stdout)
        
        assert data["id"] == "test1234"
        assert "path" in data
        assert data["path"].endswith("test1234.md")
        
        # Range should cover the body (after frontmatter is stripped by vault)
        assert data["range"]["start"] == 0
        assert data["range"]["end"] > data["range"]["start"]
        
        # Lines should be reasonable
        assert data["lines"]["start"] >= 1
        assert data["lines"]["end"] > data["lines"]["start"]


def test_locate_heading_slug():
    """Test locating with heading slug anchor."""
    with tempfile.TemporaryDirectory() as tmpdir:
        vault = Path(tmpdir)
        note_path = vault / "test1234.md"
        note_path.write_text("""---
id: test1234
---

# Test

## My Section

Section content here.

## Another Section

More content.
""")
        
        result = subprocess.run(
            ["hypo", "--vault", str(vault), "locate", "test1234#my-section"],
            capture_output=True,
            text=True,
        )
        
        assert result.returncode == 0
        data = json.loads(result.stdout)
        
        assert data["id"] == "test1234"
        assert "anchor" in data
        assert data["anchor"]["kind"] == "heading"
        assert data["anchor"]["value"] == "my-section"
        
        # Range should be reasonable
        assert data["range"]["start"] > 0
        assert data["range"]["end"] > data["range"]["start"]


def test_locate_block_label():
    """Test locating with block label anchor."""
    with tempfile.TemporaryDirectory() as tmpdir:
        vault = Path(tmpdir)
        note_path = vault / "test1234.md"
        note_path.write_text("""---
id: test1234
---

# Test

```python ^mycode
def hello():
    print("world")
```

More text.
""")
        
        result = subprocess.run(
            ["hypo", "--vault", str(vault), "locate", "test1234#^mycode"],
            capture_output=True,
            text=True,
        )
        
        assert result.returncode == 0
        data = json.loads(result.stdout)
        
        assert data["id"] == "test1234"
        assert "anchor" in data
        assert data["anchor"]["kind"] == "block"
        assert data["anchor"]["value"] == "mycode"
        
        # Range should be for the code block
        assert data["range"]["start"] > 0
        assert data["range"]["end"] > data["range"]["start"]


def test_locate_tsv_format():
    """Test TSV output format."""
    with tempfile.TemporaryDirectory() as tmpdir:
        vault = Path(tmpdir)
        note_path = vault / "test1234.md"
        note_path.write_text("""---
id: test1234
---

# Test

Content here.
""")
        
        result = subprocess.run(
            ["hypo", "--vault", str(vault), "locate", "test1234", "--format", "tsv"],
            capture_output=True,
            text=True,
        )
        
        assert result.returncode == 0
        parts = result.stdout.strip().split("\t")
        
        assert parts[0] == "test1234"
        assert parts[1].endswith("test1234.md")
        # Should have start, end, start_line, end_line
        assert len(parts) >= 3


def test_locate_missing_note():
    """Test locating nonexistent note returns error."""
    with tempfile.TemporaryDirectory() as tmpdir:
        vault = Path(tmpdir)
        
        result = subprocess.run(
            ["hypo", "--vault", str(vault), "locate", "nonexistent"],
            capture_output=True,
            text=True,
        )
        
        assert result.returncode == 1
        assert "not found" in result.stderr


def test_locate_missing_anchor():
    """Test locating with nonexistent anchor returns error."""
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
            ["hypo", "--vault", str(vault), "locate", "test1234#^nonexistent"],
            capture_output=True,
            text=True,
        )
        
        assert result.returncode == 1
        assert "not found" in result.stderr
