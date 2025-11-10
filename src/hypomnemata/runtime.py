"""Runtime wiring helper for CLI applications."""

from dataclasses import dataclass
from pathlib import Path

from .adapters.fs_storage import FsStorage
from .adapters.idgen import HexId
from .adapters.markdown_parser import MarkdownParser
from .adapters.resolver_index import DefaultResolver
from .adapters.sqlite_index import SQLiteIndex
from .adapters.yaml_codec import MarkdownNoteCodec, YamlFrontmatter
from .config import HypoConfig, load_config
from .core.ports import Index
from .core.vault import Vault


@dataclass
class Runtime:
    """Container for all wired components."""
    vault: Vault
    index: Index
    resolver: DefaultResolver
    idgen: HexId
    config: HypoConfig


def build_runtime(
    vault_path: Path | None = None,
    db_path: Path | None = None,
    config_path: Path | None = None,
) -> Runtime:
    """Build and wire all components for a vault."""
    # Load configuration
    config = load_config(config_path=config_path, vault_path=vault_path)
    
    # Use config values if CLI args not provided
    if vault_path is None:
        vault_path = config.vault.root
    if db_path is None:
        db_path = config.vault.db
    
    storage = FsStorage(vault_path)
    codec = MarkdownNoteCodec(YamlFrontmatter())
    parser = MarkdownParser()
    vault = Vault(storage, parser, codec)
    
    index = SQLiteIndex(db_path=db_path, vault_path=vault_path, vault=vault)
    resolver = DefaultResolver(vault)
    idgen = HexId(nbytes=config.id.bytes)
    
    return Runtime(
        vault=vault,
        index=index,
        resolver=resolver,
        idgen=idgen,
        config=config,
    )
