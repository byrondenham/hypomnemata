"""ID generation strategies for import."""

import hashlib
import secrets
from pathlib import Path

from ..core.utils import slugify


class RandomIdGenerator:
    """Generate random cryptographic IDs."""
    
    def __init__(self, nbytes: int = 6):
        self.nbytes = nbytes
    
    def generate(self, source_path: str, content: str | None = None) -> str:
        """Generate a random hex ID (ignores source_path and content)."""
        return secrets.token_hex(self.nbytes)


class HashIdGenerator:
    """Generate deterministic IDs from path or content."""
    
    def __init__(self, nbytes: int = 6, use_content: bool = False):
        self.nbytes = nbytes
        self.use_content = use_content
    
    def generate(self, source_path: str, content: str | None = None) -> str:
        """Generate a hash-based ID from path or content."""
        if self.use_content and content:
            data = content.encode('utf-8')
        else:
            # Use normalized path
            data = str(Path(source_path).as_posix()).encode('utf-8')
        
        hash_digest = hashlib.sha256(data).hexdigest()
        # Take first N bytes worth of hex characters
        return hash_digest[:self.nbytes * 2]


class SlugIdGenerator:
    """Generate slug-based IDs from filename (not recommended for Hypo)."""
    
    def __init__(self, max_length: int = 50):
        self.max_length = max_length
    
    def generate(self, source_path: str, content: str | None = None) -> str:
        """Generate a slug-based ID from the filename (ignores content)."""
        path = Path(source_path)
        # Use stem (filename without extension)
        stem = path.stem
        slug = slugify(stem)
        
        # Truncate if too long
        if len(slug) > self.max_length:
            slug = slug[:self.max_length].rstrip('-')
        
        return slug


def get_id_generator(strategy: str, nbytes: int = 6) -> RandomIdGenerator | HashIdGenerator | SlugIdGenerator:
    """Factory function to get ID generator based on strategy."""
    if strategy == "random":
        return RandomIdGenerator(nbytes=nbytes)
    elif strategy == "hash":
        return HashIdGenerator(nbytes=nbytes)
    elif strategy == "slug":
        return SlugIdGenerator()
    else:
        raise ValueError(f"Unknown ID strategy: {strategy}")
