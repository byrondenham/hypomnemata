"""Plan phase: scan source and build import plan."""

import csv
import json
from collections import defaultdict
from pathlib import Path
from typing import Any

import yaml

from .id_strategies import get_id_generator
from .models import ImportItem, ImportPlan


def extract_metadata(file_path: Path, title_key: str = "core/title", 
                      alias_keys: list[str] | None = None) -> tuple[str, list[str]]:
    """
    Extract title and aliases from a Markdown file.
    
    Returns:
        Tuple of (title, aliases)
    """
    if alias_keys is None:
        alias_keys = ["core/aliases", "aliases"]
    
    content = file_path.read_text(encoding='utf-8')
    
    # Try to parse YAML frontmatter
    title = ""
    aliases: list[str] = []
    
    if content.startswith("---\n"):
        # Find end of frontmatter
        end_idx = content.find("\n---\n", 4)
        if end_idx > 0:
            frontmatter_str = content[4:end_idx]
            try:
                frontmatter = yaml.safe_load(frontmatter_str)
                if isinstance(frontmatter, dict):
                    # Extract title
                    for key in [title_key, "title", "core/title"]:
                        if key in frontmatter:
                            title = str(frontmatter[key])
                            break
                    
                    # Extract aliases
                    for key in alias_keys:
                        if key in frontmatter:
                            alias_val = frontmatter[key]
                            if isinstance(alias_val, list):
                                aliases = [str(a) for a in alias_val]
                            elif isinstance(alias_val, str):
                                aliases = [alias_val]
                            break
            except yaml.YAMLError:
                pass  # Invalid frontmatter, fall back
    
    # If no title from frontmatter, extract from first heading or first line
    if not title:
        body_start = end_idx + 5 if content.startswith("---\n") and end_idx > 0 else 0
        body = content[body_start:].strip()
        
        if body:
            lines = body.split('\n')
            for line in lines:
                line = line.strip()
                if line.startswith('# '):
                    # First H1 heading
                    title = line[2:].strip()
                    break
                elif line and not line.startswith('#'):
                    # First non-empty, non-heading line
                    title = line[:100]  # Limit length
                    break
    
    # Fallback to filename if still no title
    if not title:
        title = file_path.stem
    
    return title, aliases


def build_import_plan(
    src_dir: Path,
    glob_pattern: str = "**/*.md",
    id_strategy: str = "random",
    id_bytes: int = 6,
    title_key: str = "core/title",
    alias_keys: list[str] | None = None,
    strict: bool = False,
) -> ImportPlan:
    """
    Scan source directory and build import plan.
    
    Args:
        src_dir: Source directory to scan
        glob_pattern: File pattern to match
        id_strategy: ID generation strategy (random, hash, slug)
        id_bytes: Number of bytes for random/hash IDs
        title_key: Frontmatter key for title
        alias_keys: Frontmatter keys for aliases
        strict: Fail on any conflicts
    
    Returns:
        ImportPlan with items and detected conflicts
    """
    plan = ImportPlan(
        src=str(src_dir.absolute()),
        id_strategy=id_strategy,  # type: ignore
    )
    
    id_gen = get_id_generator(id_strategy, nbytes=id_bytes)
    
    # Track titles and aliases for conflict detection
    title_to_paths: dict[str, list[str]] = defaultdict(list)
    alias_to_paths: dict[str, list[str]] = defaultdict(list)
    used_ids: set[str] = set()
    
    # Scan all matching files
    for file_path in sorted(src_dir.glob(glob_pattern)):
        if not file_path.is_file():
            continue
        
        # Get relative path for storage
        rel_path = file_path.relative_to(src_dir)
        
        # Extract metadata
        try:
            title, aliases = extract_metadata(file_path, title_key, alias_keys)
        except Exception as e:
            plan.items.append(ImportItem(
                src=str(rel_path),
                id="",
                title="",
                status="error",
                reason=f"Failed to parse: {e}"
            ))
            continue
        
        # Generate ID (ensure uniqueness for random strategy)
        max_attempts = 100
        for _ in range(max_attempts):
            content = file_path.read_text(encoding='utf-8') if id_strategy == "hash" else None
            candidate_id = id_gen.generate(str(file_path), content)
            if candidate_id not in used_ids:
                break
        else:
            # Unlikely but handle it
            plan.items.append(ImportItem(
                src=str(rel_path),
                id="",
                title=title,
                aliases=aliases,
                status="error",
                reason="Failed to generate unique ID"
            ))
            continue
        
        used_ids.add(candidate_id)
        
        # Track for conflict detection
        title_to_paths[title].append(str(rel_path))
        for alias in aliases:
            alias_to_paths[alias].append(str(rel_path))
        
        # Add to plan
        plan.items.append(ImportItem(
            src=str(rel_path),
            id=candidate_id,
            title=title,
            aliases=aliases,
            status="ok",
        ))
    
    # Detect conflicts
    for title, paths in title_to_paths.items():
        if len(paths) > 1:
            plan.conflicts[f"title:{title}"] = paths
            # Mark items as conflicted
            for item in plan.items:
                if item.src in paths and item.title == title:
                    item.status = "conflict"
                    item.reason = f"Duplicate title: '{title}'"
    
    for alias, paths in alias_to_paths.items():
        if len(paths) > 1:
            plan.conflicts[f"alias:{alias}"] = paths
            # Mark items as conflicted
            for item in plan.items:
                if item.src in paths and alias in item.aliases:
                    item.status = "conflict"
                    if item.reason:
                        item.reason += f"; Duplicate alias: '{alias}'"
                    else:
                        item.reason = f"Duplicate alias: '{alias}'"
    
    return plan


def save_plan_json(plan: ImportPlan, output_path: Path) -> None:
    """Save plan to JSON file."""
    data: dict[str, Any] = {
        "version": plan.version,
        "generated_at": plan.generated_at,
        "src": plan.src,
        "id_strategy": plan.id_strategy,
        "items": [
            {
                "src": item.src,
                "id": item.id,
                "title": item.title,
                "aliases": item.aliases,
                "status": item.status,
                "reason": item.reason,
            }
            for item in plan.items
        ],
        "conflicts": plan.conflicts,
    }
    
    with output_path.open('w', encoding='utf-8') as f:
        json.dump(data, f, indent=2, ensure_ascii=False)


def save_plan_csv(plan: ImportPlan, output_path: Path) -> None:
    """Save plan to CSV file for human review."""
    with output_path.open('w', newline='', encoding='utf-8') as f:
        writer = csv.writer(f)
        writer.writerow(["src", "id", "title", "aliases", "status", "reason"])
        
        for item in plan.items:
            writer.writerow([
                item.src,
                item.id,
                item.title,
                "|".join(item.aliases) if item.aliases else "",
                item.status,
                item.reason or "",
            ])


def load_plan_json(input_path: Path) -> ImportPlan:
    """Load plan from JSON file."""
    with input_path.open('r', encoding='utf-8') as f:
        data = json.load(f)
    
    plan = ImportPlan(
        version=data.get("version", 1),
        generated_at=data.get("generated_at", ""),
        src=data.get("src", ""),
        id_strategy=data.get("id_strategy", "random"),
        conflicts=data.get("conflicts", {}),
    )
    
    for item_data in data.get("items", []):
        plan.items.append(ImportItem(
            src=item_data["src"],
            id=item_data["id"],
            title=item_data["title"],
            aliases=item_data.get("aliases", []),
            status=item_data.get("status", "ok"),
            reason=item_data.get("reason"),
        ))
    
    return plan
