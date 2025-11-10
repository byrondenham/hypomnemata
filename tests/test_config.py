"""Tests for configuration loading."""

import tempfile
from pathlib import Path

from hypomnemata.config import load_config


def test_load_config_defaults():
    """Test loading config with defaults when no file exists."""
    config = load_config()
    
    # Should use defaults
    assert config.vault.root == Path("./vault")
    assert config.id.bytes == 6
    assert config.ui.colors is True


def test_load_config_from_file():
    """Test loading config from a file."""
    with tempfile.TemporaryDirectory() as tmpdir:
        config_path = Path(tmpdir) / "hypo.toml"
        config_path.write_text("""
[vault]
root = "my-vault"
db = "custom.db"

[id]
bytes = 8

[export.quartz]
out = "output"
katex = { auto = false }

[ui]
colors = false
""")
        
        config = load_config(config_path=config_path)
        
        assert config.vault.root == Path("my-vault")
        assert config.vault.db == Path("custom.db")
        assert config.id.bytes == 8
        assert config.export.quartz is not None
        assert config.export.quartz.out == Path("output")
        assert config.export.quartz.katex.auto is False
        assert config.ui.colors is False


def test_load_config_search_cwd():
    """Test config search in current working directory."""
    with tempfile.TemporaryDirectory() as tmpdir:
        import os
        orig_cwd = os.getcwd()
        try:
            os.chdir(tmpdir)
            config_path = Path(tmpdir) / "hypo.toml"
            config_path.write_text("""
[id]
bytes = 10
""")
            
            config = load_config()
            assert config.id.bytes == 10
        finally:
            os.chdir(orig_cwd)


def test_load_config_search_vault():
    """Test config search in vault directory."""
    with tempfile.TemporaryDirectory() as tmpdir:
        vault_path = Path(tmpdir) / "vault"
        vault_path.mkdir()
        config_path = vault_path / "hypo.toml"
        config_path.write_text("""
[id]
bytes = 12
""")
        
        config = load_config(vault_path=vault_path)
        assert config.id.bytes == 12
