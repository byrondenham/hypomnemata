"""Text hygiene utilities for Hypomnemata notes."""

import re
import textwrap


def normalize_text(
    text: str,
    wrap: int = 0,
    eol: str | None = None,
    strip_trailing: bool = False,
    ensure_final_eol: bool = False,
) -> str:
    """Apply text hygiene transformations.
    
    Args:
        text: Input text
        wrap: Column width for paragraph wrapping (0 disables)
        eol: Line ending style ('lf', 'crlf', 'native', or None to preserve)
        strip_trailing: Remove trailing whitespace from lines
        ensure_final_eol: Ensure file ends with newline
    
    Returns:
        Normalized text
    """
    result = text
    
    # Wrap paragraphs if requested
    if wrap > 0:
        result = _wrap_paragraphs(result, wrap)
    
    # Normalize line endings
    if eol:
        if eol == 'lf':
            result = result.replace('\r\n', '\n').replace('\r', '\n')
        elif eol == 'crlf':
            result = result.replace('\r\n', '\n').replace('\r', '\n')
            result = result.replace('\n', '\r\n')
        elif eol == 'native':
            import os
            if os.name == 'nt':
                result = result.replace('\r\n', '\n').replace('\r', '\n')
                result = result.replace('\n', '\r\n')
            else:
                result = result.replace('\r\n', '\n').replace('\r', '\n')
    
    # Strip trailing whitespace
    if strip_trailing:
        lines = result.splitlines(keepends=True)
        stripped_lines = []
        for line in lines:
            # Preserve the line ending
            line_content = line.rstrip('\r\n')
            line_ending = line[len(line_content):]
            stripped_lines.append(line_content.rstrip() + line_ending)
        result = ''.join(stripped_lines)
    
    # Ensure final EOL
    if ensure_final_eol and result and not result.endswith(('\n', '\r\n')):
        if eol == 'crlf':
            result += '\r\n'
        else:
            result += '\n'
    
    return result


def _wrap_paragraphs(text: str, width: int) -> str:
    """Wrap paragraphs at given width, avoiding code blocks, headings, lists, etc."""
    lines = text.splitlines(keepends=True)
    result = []
    i = 0
    
    while i < len(lines):
        line = lines[i]
        line_stripped = line.rstrip('\n\r')
        
        # Check for code fence
        if line_stripped.startswith('```'):
            # Copy fence and everything until closing
            result.append(line)
            i += 1
            while i < len(lines):
                result.append(lines[i])
                if lines[i].rstrip('\n\r').startswith('```'):
                    i += 1
                    break
                i += 1
            continue
        
        # Check for heading
        if re.match(r'^#{1,6}\s', line_stripped):
            result.append(line)
            i += 1
            continue
        
        # Check for list item
        if re.match(r'^\s*[-*+]\s', line_stripped) or re.match(r'^\s*\d+\.\s', line_stripped):
            result.append(line)
            i += 1
            continue
        
        # Check for blockquote
        if line_stripped.startswith('>'):
            result.append(line)
            i += 1
            continue
        
        # Check for horizontal rule
        if re.match(r'^\s*[-*_]{3,}\s*$', line_stripped):
            result.append(line)
            i += 1
            continue
        
        # Check for blank line
        if not line_stripped:
            result.append(line)
            i += 1
            continue
        
        # Check for math block ($$)
        if line_stripped.startswith('$$'):
            result.append(line)
            i += 1
            while i < len(lines):
                result.append(lines[i])
                if lines[i].rstrip('\n\r').startswith('$$'):
                    i += 1
                    break
                i += 1
            continue
        
        # This is a paragraph - collect consecutive non-blank lines
        paragraph_lines = []
        while i < len(lines):
            curr_line = lines[i]
            curr_stripped = curr_line.rstrip('\n\r')
            
            # Stop at blank line or special syntax
            if (not curr_stripped or 
                curr_stripped.startswith('```') or
                re.match(r'^#{1,6}\s', curr_stripped) or
                re.match(r'^\s*[-*+]\s', curr_stripped) or
                re.match(r'^\s*\d+\.\s', curr_stripped) or
                curr_stripped.startswith('>') or
                re.match(r'^\s*[-*_]{3,}\s*$', curr_stripped) or
                curr_stripped.startswith('$$')):
                break
            
            paragraph_lines.append(curr_stripped)
            i += 1
        
        # Wrap the paragraph
        if paragraph_lines:
            paragraph_text = ' '.join(paragraph_lines)
            wrapped = textwrap.fill(
                paragraph_text,
                width=width,
                break_long_words=False,
                break_on_hyphens=False,
            )
            result.append(wrapped + '\n')
    
    return ''.join(result)
