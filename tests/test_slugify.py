"""Tests for slugify utility function."""

from hypomnemata.core.utils import slugify


def test_slugify_basic():
    """Test basic slugification."""
    assert slugify("Parallel transport") == "parallel-transport"
    assert slugify("Hello World") == "hello-world"


def test_slugify_unicode():
    """Test unicode normalization."""
    # En dash (–) should be normalized
    assert slugify("Riemann–Christoffel symbols") == "riemann-christoffel-symbols"
    # Em dash (—) should also work
    assert slugify("Test—Example") == "test-example"


def test_slugify_punctuation():
    """Test punctuation removal."""
    assert slugify("Hello, World!") == "hello-world"
    assert slugify("Test (with parentheses)") == "test-with-parentheses"
    assert slugify("Question?") == "question"


def test_slugify_multiple_spaces():
    """Test multiple spaces converted to single dash."""
    assert slugify("Multiple   spaces   here") == "multiple-spaces-here"


def test_slugify_multiple_dashes():
    """Test multiple dashes collapsed to single dash."""
    assert slugify("Test---Example") == "test-example"
    assert slugify("Test - - Example") == "test-example"


def test_slugify_leading_trailing():
    """Test leading/trailing dashes are stripped."""
    assert slugify(" Leading and trailing ") == "leading-and-trailing"
    assert slugify("-Already-Has-Dashes-") == "already-has-dashes"


def test_slugify_empty():
    """Test empty string."""
    assert slugify("") == ""
    assert slugify("   ") == ""


def test_slugify_special_chars():
    """Test special character handling."""
    assert slugify("File & Folder") == "file-folder"
    assert slugify("C++ Programming") == "c-programming"
    assert slugify("Node.js") == "nodejs"
