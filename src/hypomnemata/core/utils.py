"""Utility functions for hypomnemata."""

import re
import unicodedata


def slugify(text: str) -> str:
    """
    Convert text to a URL-safe slug.
    
    - Lowercase
    - Unicode normalize (NFKD), drop combining marks
    - Remove punctuation except spaces and hyphens
    - Convert whitespace to single `-`
    - Collapse multiple `-` to single, strip leading/trailing `-`
    
    Examples:
        >>> slugify("Parallel transport")
        'parallel-transport'
        >>> slugify("Riemann–Christoffel symbols")
        'riemann-christoffel-symbols'
    """
    # Lowercase
    text = text.lower()
    
    # Replace various dash-like characters with regular hyphen
    # En dash (–), em dash (—), and other dashes
    text = text.replace('–', '-').replace('—', '-').replace('−', '-')
    
    # Unicode normalize (NFKD) and drop combining marks
    text = unicodedata.normalize('NFKD', text)
    text = ''.join(c for c in text if not unicodedata.combining(c))
    
    # Remove punctuation except spaces and hyphens
    # Keep alphanumeric, spaces, and hyphens
    text = re.sub(r'[^\w\s-]', '', text)
    
    # Convert whitespace to single `-`
    text = re.sub(r'\s+', '-', text)
    
    # Collapse multiple `-` to single
    text = re.sub(r'-+', '-', text)
    
    # Strip leading/trailing `-`
    text = text.strip('-')
    
    return text
