"""Tests for version information."""

import subprocess


def test_version_flag():
    """Test that --version flag works and shows version."""
    result = subprocess.run(
        ["hypo", "--version"],
        capture_output=True,
        text=True,
    )
    
    assert result.returncode == 0
    assert "hypomnemata" in result.stdout
    assert "python" in result.stdout
    assert "platform" in result.stdout
    assert "commit" in result.stdout


def test_version_module():
    """Test that version is accessible from module."""
    from hypomnemata import __version__
    
    assert __version__
    assert isinstance(__version__, str)
    # Should be in SemVer format
    parts = __version__.split('.')
    assert len(parts) >= 2  # At least MAJOR.MINOR
