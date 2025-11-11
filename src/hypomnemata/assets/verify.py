"""Asset verification utilities."""

import hashlib
from dataclasses import dataclass, field
from pathlib import Path

from .scanner import AssetRef, scan_asset_refs


@dataclass
class AssetReport:
    """Report of asset verification."""
    
    total_refs: int = 0
    missing_refs: list[AssetRef] = field(default_factory=list)
    dangling_files: list[Path] = field(default_factory=list)
    file_hashes: dict[Path, str] = field(default_factory=dict)


def verify_assets(
    vault_root: Path,
    notes: dict[str, str],  # note_id -> note_text
    assets_dir: Path | None = None,
    compute_hashes: bool = False,
    write_sidecars: bool = False,
) -> AssetReport:
    """Verify asset integrity in a vault.
    
    Args:
        vault_root: Root directory of the vault
        notes: Dictionary of note_id -> note_text
        assets_dir: Assets directory (default: vault_root/assets)
        compute_hashes: Compute SHA256 hashes for assets
        write_sidecars: Write .sha256 sidecar files
    
    Returns:
        AssetReport with verification results
    """
    if assets_dir is None:
        assets_dir = vault_root / "assets"
    
    report = AssetReport()
    
    # Collect all asset references
    all_refs: list[AssetRef] = []
    for note_id, note_text in notes.items():
        refs = scan_asset_refs(note_id, note_text, vault_root, assets_dir)
        all_refs.extend(refs)
    
    report.total_refs = len(all_refs)
    
    # Track which files are referenced
    referenced_files: set[Path] = set()
    
    # Check for missing referenced files
    for ref in all_refs:
        if ref.resolved_path:
            if not ref.resolved_path.exists():
                report.missing_refs.append(ref)
            else:
                referenced_files.add(ref.resolved_path)
                
                # Compute hash if requested
                if compute_hashes and ref.resolved_path not in report.file_hashes:
                    hash_val = compute_file_hash(ref.resolved_path)
                    report.file_hashes[ref.resolved_path] = hash_val
                    
                    # Write sidecar if requested
                    if write_sidecars:
                        sidecar_path = ref.resolved_path.with_suffix(
                            ref.resolved_path.suffix + '.sha256'
                        )
                        _write_sidecar_atomic(sidecar_path, hash_val)
    
    # Find dangling files (in assets dir but never referenced)
    if assets_dir.exists():
        for asset_file in assets_dir.rglob('*'):
            if asset_file.is_file() and not asset_file.name.endswith('.sha256'):
                # Debug: check why this is dangling
                is_referenced = asset_file in referenced_files
                if not is_referenced:
                    # Try to see if it matches any path when resolved
                    for ref_path in referenced_files:
                        if asset_file.resolve() == ref_path.resolve():
                            is_referenced = True
                            break
                
                if not is_referenced:
                    report.dangling_files.append(asset_file)
    
    return report


def compute_file_hash(file_path: Path) -> str:
    """Compute SHA256 hash of a file."""
    sha256 = hashlib.sha256()
    with file_path.open('rb') as f:
        # Read in chunks for large files
        while chunk := f.read(8192):
            sha256.update(chunk)
    return sha256.hexdigest()


def _write_sidecar_atomic(sidecar_path: Path, hash_val: str) -> None:
    """Write a sidecar file atomically."""
    tmp_path = sidecar_path.with_suffix('.tmp')
    try:
        tmp_path.write_text(hash_val + '\n', encoding='utf-8')
        tmp_path.replace(sidecar_path)
    except Exception:
        if tmp_path.exists():
            tmp_path.unlink()
        raise


def format_report(report: AssetReport, json_output: bool = False) -> str:
    """Format an asset report for display.
    
    Args:
        report: The asset report
        json_output: If True, output JSON format
    
    Returns:
        Formatted report string
    """
    if json_output:
        import json
        return json.dumps({
            "total_refs": report.total_refs,
            "missing_count": len(report.missing_refs),
            "missing_refs": [
                {
                    "note_id": ref.note_id,
                    "asset_path": ref.asset_path,
                    "ref_type": ref.ref_type,
                }
                for ref in report.missing_refs
            ],
            "dangling_count": len(report.dangling_files),
            "dangling_files": [str(f) for f in report.dangling_files],
            "hashes": {str(k): v for k, v in report.file_hashes.items()},
        }, indent=2)
    else:
        lines = []
        lines.append(f"Asset Verification Report")
        lines.append(f"========================")
        lines.append(f"Total references: {report.total_refs}")
        lines.append(f"Missing references: {len(report.missing_refs)}")
        lines.append(f"Dangling files: {len(report.dangling_files)}")
        
        if report.missing_refs:
            lines.append("")
            lines.append("Missing Files:")
            for ref in report.missing_refs:
                lines.append(f"  {ref.note_id}: {ref.asset_path} ({ref.ref_type})")
        
        if report.dangling_files:
            lines.append("")
            lines.append("Dangling Files:")
            for file in report.dangling_files:
                lines.append(f"  {file}")
        
        if report.file_hashes:
            lines.append("")
            lines.append(f"Computed {len(report.file_hashes)} file hashes")
        
        return '\n'.join(lines)
