"""Tests for text hygiene."""

from hypomnemata.format.text import normalize_text


def test_normalize_text_strip_trailing():
    """Test trailing whitespace removal."""
    text = "Line 1  \nLine 2\t\nLine 3   \n"
    result = normalize_text(text, strip_trailing=True)
    assert result == "Line 1\nLine 2\nLine 3\n"


def test_normalize_text_ensure_final_eol():
    """Test ensuring final newline."""
    text = "Line 1\nLine 2"
    result = normalize_text(text, ensure_final_eol=True)
    assert result.endswith("\n")


def test_normalize_text_eol_lf():
    """Test LF normalization."""
    text = "Line 1\r\nLine 2\rLine 3\n"
    result = normalize_text(text, eol="lf")
    assert "\r" not in result
    assert "Line 1\nLine 2\nLine 3\n" == result


def test_normalize_text_eol_crlf():
    """Test CRLF normalization."""
    text = "Line 1\nLine 2\n"
    result = normalize_text(text, eol="crlf")
    assert result == "Line 1\r\nLine 2\r\n"


def test_normalize_text_wrap_simple():
    """Test simple paragraph wrapping."""
    text = "This is a very long line that should be wrapped at a certain column width to make it more readable.\n"  # noqa: E501
    result = normalize_text(text, wrap=40)

    lines = result.split("\n")
    # Check that lines are wrapped
    assert any(len(line) <= 40 for line in lines if line)


def test_normalize_text_wrap_preserves_headings():
    """Test that headings are not wrapped."""
    text = "# This is a very long heading that should not be wrapped even if it exceeds the column width\n\nParagraph text.\n"  # noqa: E501
    result = normalize_text(text, wrap=40)

    # Heading should be preserved
    assert (
        "# This is a very long heading that should not be wrapped even if it exceeds the column width"  # noqa: E501
        in result
    )  # noqa: E501


def test_normalize_text_wrap_preserves_code_fence():
    """Test that code fences are not wrapped."""
    text = """```python
def very_long_function_name_that_should_not_be_wrapped_because_it_is_code():
    pass
```
"""
    result = normalize_text(text, wrap=40)

    # Code should be preserved
    assert "def very_long_function_name_that_should_not_be_wrapped_because_it_is_code():" in result


def test_normalize_text_wrap_preserves_lists():
    """Test that lists are not wrapped."""
    text = "- This is a very long list item that should not be wrapped\n- Another item\n"
    result = normalize_text(text, wrap=40)

    # List items should be preserved
    assert "- This is a very long list item that should not be wrapped" in result


def test_normalize_text_combined():
    """Test combining multiple transformations."""
    text = "Line 1  \r\nLine 2\t\r\nLine 3"
    result = normalize_text(
        text,
        eol="lf",
        strip_trailing=True,
        ensure_final_eol=True,
    )

    assert result == "Line 1\nLine 2\nLine 3\n"
