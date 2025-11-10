"""Runtime wiring helper for CLI applications."""

from dataclasses import dataclass
from pathlib import Path

from .adapters.fs_storage import FsStorage
from .adapters.idgen import HexId
from .adapters.markdown_parser import MarkdownParser
from .adapters.resolver_index import DefaultResolver, InMemoryIndex
from .adapters.yaml_codec import MarkdownNoteCodec, YamlFrontmatter
from .core.ports import Index
from .core.vault import Vault


@dataclass
class Runtime:
    """Container for all wired components."""
    vault: Vault
    index: Index
    resolver: DefaultResolver
    idgen: HexId


def build_runtime(vault_path: Path) -> Runtime:
    """Build and wire all components for a vault."""
    storage = FsStorage(vault_path)
    codec = MarkdownNoteCodec(YamlFrontmatter())
    parser = MarkdownParser()
    vault = Vault(storage, parser, codec)
    
    index = InMemoryIndex(vault)
    resolver = DefaultResolver(vault)
    idgen = HexId()
    
    return Runtime(
        vault=vault,
        index=index,
        resolver=resolver,
        idgen=idgen,
    )
