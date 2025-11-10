"""Tests for Quartz export with slice-based transclusion."""

import tempfile
from pathlib import Path

from hypomnemata.adapters.fs_storage import FsStorage
from hypomnemata.adapters.markdown_parser import MarkdownParser
from hypomnemata.adapters.yaml_codec import MarkdownNoteCodec, YamlFrontmatter
from hypomnemata.core.vault import Vault
from hypomnemata.export.quartz import QuartzAdapter


def test_quartz_transclusion_whole_note():
    """Test Quartz export with whole note transclusion."""
    with tempfile.TemporaryDirectory() as tmpdir:
        vault_dir = Path(tmpdir) / "vault"
        vault_dir.mkdir()
        
        # Create target note
        target = vault_dir / "target123.md"
        target.write_text("""---
id: target123
---

# Target

Target content.
""")
        
        # Create source note with transclusion
        source = vault_dir / "source456.md"
        source.write_text("""---
id: source456
---

# Source

![[target123]]

After transclusion.
""")
        
        # Set up vault and export
        storage = FsStorage(vault_dir)
        parser = MarkdownParser()
        codec = MarkdownNoteCodec(YamlFrontmatter())
        vault = Vault(storage, parser, codec)
        
        out_dir = Path(tmpdir) / "out"
        adapter = QuartzAdapter(vault, out_dir)
        adapter.export_all()
        
        # Check exported source
        exported = (out_dir / "source456" / "index.md").read_text()
        
        # Should have transcluded content
        assert "# Target" in exported
        assert "Target content." in exported
        # Original source content should be there too
        assert "# Source" in exported
        assert "After transclusion." in exported


def test_quartz_transclusion_with_anchor():
    """Test Quartz export with anchor-based transclusion."""
    with tempfile.TemporaryDirectory() as tmpdir:
        vault_dir = Path(tmpdir) / "vault"
        vault_dir.mkdir()
        
        # Create target note with labeled section
        target = vault_dir / "target123.md"
        target.write_text("""---
id: target123
---

# Target

Before section.

## Important Section ^label

Section content.

## Other Section

Other content.
""")
        
        # Create source note with labeled transclusion
        source = vault_dir / "source456.md"
        source.write_text("""---
id: source456
---

# Source

![[target123#^label]]

After transclusion.
""")
        
        # Set up vault and export
        storage = FsStorage(vault_dir)
        parser = MarkdownParser()
        codec = MarkdownNoteCodec(YamlFrontmatter())
        vault = Vault(storage, parser, codec)
        
        out_dir = Path(tmpdir) / "out"
        adapter = QuartzAdapter(vault, out_dir)
        adapter.export_all()
        
        # Check exported source
        exported = (out_dir / "source456" / "index.md").read_text()
        
        # Should have transcluded section only
        assert "## Important Section ^label" in exported
        assert "Section content." in exported
        # Should not have other sections
        assert "Before section." not in exported
        assert "## Other Section" not in exported


def test_quartz_transclusion_fence_block():
    """Test Quartz export with fenced block transclusion."""
    with tempfile.TemporaryDirectory() as tmpdir:
        vault_dir = Path(tmpdir) / "vault"
        vault_dir.mkdir()
        
        # Create target note with fenced block
        target = vault_dir / "target123.md"
        target.write_text("""---
id: target123
---

# Target

```python ^code
def hello():
    print("world")
```

More content.
""")
        
        # Create source note with fence transclusion
        source = vault_dir / "source456.md"
        source.write_text("""---
id: source456
---

# Source

![[target123#^code]]

After transclusion.
""")
        
        # Set up vault and export
        storage = FsStorage(vault_dir)
        parser = MarkdownParser()
        codec = MarkdownNoteCodec(YamlFrontmatter())
        vault = Vault(storage, parser, codec)
        
        out_dir = Path(tmpdir) / "out"
        adapter = QuartzAdapter(vault, out_dir)
        adapter.export_all()
        
        # Check exported source
        exported = (out_dir / "source456" / "index.md").read_text()
        
        # Should have transcluded fence
        assert "```python ^code" in exported
        assert 'def hello():' in exported
        # Should not have text after fence
        assert "More content." not in exported


def test_quartz_transclusion_missing_note():
    """Test Quartz export with missing target note."""
    with tempfile.TemporaryDirectory() as tmpdir:
        vault_dir = Path(tmpdir) / "vault"
        vault_dir.mkdir()
        
        # Create source note with transclusion to missing note
        source = vault_dir / "source456.md"
        source.write_text("""---
id: source456
---

# Source

![[missing123]]

After transclusion.
""")
        
        # Set up vault and export
        storage = FsStorage(vault_dir)
        parser = MarkdownParser()
        codec = MarkdownNoteCodec(YamlFrontmatter())
        vault = Vault(storage, parser, codec)
        
        out_dir = Path(tmpdir) / "out"
        adapter = QuartzAdapter(vault, out_dir)
        adapter.export_all()
        
        # Check exported source
        exported = (out_dir / "source456" / "index.md").read_text()
        
        # Should have error message
        assert "> **Hypo:** missing note `missing123`" in exported


def test_quartz_transclusion_missing_anchor():
    """Test Quartz export with missing anchor."""
    with tempfile.TemporaryDirectory() as tmpdir:
        vault_dir = Path(tmpdir) / "vault"
        vault_dir.mkdir()
        
        # Create target note without the label
        target = vault_dir / "target123.md"
        target.write_text("""---
id: target123
---

# Target

Content.
""")
        
        # Create source note with transclusion to missing anchor
        source = vault_dir / "source456.md"
        source.write_text("""---
id: source456
---

# Source

![[target123#^missing]]

After transclusion.
""")
        
        # Set up vault and export
        storage = FsStorage(vault_dir)
        parser = MarkdownParser()
        codec = MarkdownNoteCodec(YamlFrontmatter())
        vault = Vault(storage, parser, codec)
        
        out_dir = Path(tmpdir) / "out"
        adapter = QuartzAdapter(vault, out_dir)
        adapter.export_all()
        
        # Check exported source
        exported = (out_dir / "source456" / "index.md").read_text()
        
        # Should have error message with anchor
        assert "> **Hypo:** missing anchor `target123#^missing`" in exported
