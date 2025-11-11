"""Tests for asset scanner."""

import pytest
from pathlib import Path

from hypomnemata.assets.scanner import scan_asset_refs


def test_scan_asset_refs_markdown_image():
    """Test scanning Markdown images."""
    text = "Here is an image: ![alt text](assets/image.png)"
    vault_root = Path("/tmp/vault")
    
    refs = scan_asset_refs("note1", text, vault_root)
    
    assert len(refs) == 1
    assert refs[0].asset_path == "assets/image.png"
    assert refs[0].ref_type == "image"
    assert refs[0].note_id == "note1"


def test_scan_asset_refs_markdown_file_link():
    """Test scanning Markdown file links."""
    text = "Download [this PDF](files/document.pdf)"
    vault_root = Path("/tmp/vault")
    
    refs = scan_asset_refs("note1", text, vault_root)
    
    assert len(refs) == 1
    assert refs[0].asset_path == "files/document.pdf"
    assert refs[0].ref_type == "file"


def test_scan_asset_refs_html_img():
    """Test scanning HTML img tags."""
    text = '<img src="assets/photo.jpg" alt="Photo">'
    vault_root = Path("/tmp/vault")
    
    refs = scan_asset_refs("note1", text, vault_root)
    
    assert len(refs) == 1
    assert refs[0].asset_path == "assets/photo.jpg"
    assert refs[0].ref_type == "html"


def test_scan_asset_refs_skips_urls():
    """Test that URLs are skipped."""
    text = """
![remote](https://example.com/image.png)
[link](http://example.com/doc.pdf)
<img src="https://example.com/photo.jpg">
"""
    vault_root = Path("/tmp/vault")
    
    refs = scan_asset_refs("note1", text, vault_root)
    
    # Should find no local assets
    assert len(refs) == 0


def test_scan_asset_refs_multiple():
    """Test scanning multiple asset references."""
    text = """
# My Note

Here's an image: ![diagram](assets/diagram.png)

And a PDF: [report](files/report.pdf)

HTML image: <img src="assets/chart.svg">
"""
    vault_root = Path("/tmp/vault")
    
    refs = scan_asset_refs("note1", text, vault_root)
    
    assert len(refs) == 3
    asset_paths = [ref.asset_path for ref in refs]
    assert "assets/diagram.png" in asset_paths
    assert "files/report.pdf" in asset_paths
    assert "assets/chart.svg" in asset_paths


def test_scan_asset_refs_relative_paths():
    """Test handling of relative paths."""
    text = """
![local](./local.png)
![parent](../parent.png)
![absolute](/absolute.png)
"""
    vault_root = Path("/tmp/vault")
    
    refs = scan_asset_refs("note1", text, vault_root)
    
    assert len(refs) == 3
