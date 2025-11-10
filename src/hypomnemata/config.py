"""Configuration loader for hypo.toml."""

from dataclasses import dataclass
from pathlib import Path
from typing import Any

try:
    import tomllib
except ImportError:
    import tomli as tomllib  # type: ignore


@dataclass
class VaultConfig:
    """Vault-specific configuration."""
    root: Path
    db: Path


@dataclass
class IdConfig:
    """ID generation configuration."""
    bytes: int = 6


@dataclass
class KatexConfig:
    """KaTeX configuration for Quartz export."""
    auto: bool = True


@dataclass
class QuartzExportConfig:
    """Quartz export configuration."""
    out: Path
    katex: KatexConfig


@dataclass
class ExportConfig:
    """Export configuration."""
    quartz: QuartzExportConfig | None = None


@dataclass
class UIConfig:
    """UI configuration."""
    colors: bool = True


@dataclass
class HypoConfig:
    """Complete hypomnemata configuration."""
    vault: VaultConfig
    id: IdConfig
    export: ExportConfig
    ui: UIConfig


def load_config(config_path: Path | None = None, vault_path: Path | None = None) -> HypoConfig:
    """
    Load configuration from hypo.toml.
    
    Search order:
    1. config_path (if provided)
    2. cwd/hypo.toml
    3. vault_path/hypo.toml
    
    Args:
        config_path: Explicit path to config file
        vault_path: Vault root path for fallback search
    
    Returns:
        HypoConfig with resolved settings
    """
    toml_data: dict[str, Any] = {}
    
    # Search for config file
    search_paths = []
    if config_path:
        search_paths.append(config_path)
    search_paths.append(Path.cwd() / "hypo.toml")
    if vault_path:
        search_paths.append(vault_path / "hypo.toml")
    
    for path in search_paths:
        if path.exists():
            with open(path, "rb") as f:
                toml_data = tomllib.load(f)
            break
    
    # Parse vault config
    vault_data = toml_data.get("vault", {})
    vault_root = Path(vault_data.get("root", vault_path or Path("./vault")))
    vault_db = Path(vault_data.get("db", vault_root / ".hypo" / "index.sqlite"))
    
    vault_config = VaultConfig(
        root=vault_root,
        db=vault_db,
    )
    
    # Parse ID config
    id_data = toml_data.get("id", {})
    id_config = IdConfig(
        bytes=id_data.get("bytes", 6)
    )
    
    # Parse export config
    export_data = toml_data.get("export", {})
    quartz_data = export_data.get("quartz", {})
    
    quartz_config = None
    if quartz_data:
        katex_data = quartz_data.get("katex", {})
        if isinstance(katex_data, dict):
            katex_config = KatexConfig(auto=katex_data.get("auto", True))
        else:
            katex_config = KatexConfig(auto=True)
        
        quartz_config = QuartzExportConfig(
            out=Path(quartz_data.get("out", "site")),
            katex=katex_config,
        )
    
    export_config = ExportConfig(quartz=quartz_config)
    
    # Parse UI config
    ui_data = toml_data.get("ui", {})
    ui_config = UIConfig(
        colors=ui_data.get("colors", True)
    )
    
    return HypoConfig(
        vault=vault_config,
        id=id_config,
        export=export_config,
        ui=ui_config,
    )
