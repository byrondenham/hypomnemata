"""Audit functionality for validating links and vault integrity."""

import re
from dataclasses import dataclass

from ..adapters.sqlite_index import SQLiteIndex
from ..core.vault import Vault


@dataclass
class AuditFinding:
    """A single audit finding/issue."""
    
    note_id: str
    severity: str  # "error", "warning", "info"
    message: str
    line: int | None = None
    column: int | None = None


@dataclass
class AuditReport:
    """Complete audit report."""
    
    findings: list[AuditFinding]
    total_notes: int
    total_links: int
    dead_links: int
    unknown_anchors: int
    duplicate_labels: int
    unmigrated_links: int = 0
    
    @property
    def has_errors(self) -> bool:
        """Check if report has any errors."""
        return any(f.severity == "error" for f in self.findings)
    
    @property
    def has_warnings(self) -> bool:
        """Check if report has any warnings."""
        return any(f.severity == "warning" for f in self.findings)


def audit_vault(
    vault: Vault,
    index: SQLiteIndex,
    strict: bool = False,
) -> AuditReport:
    """
    Audit vault for link integrity and other issues.
    
    Args:
        vault: Vault to audit
        index: SQLite index
        strict: If True, treat un-migrated links as errors
    
    Returns:
        AuditReport with findings
    """
    findings: list[AuditFinding] = []
    total_notes = 0
    total_links = 0
    dead_links = 0
    unknown_anchors = 0
    duplicate_labels = 0
    unmigrated_links = 0
    
    # Get all note IDs
    all_ids = set(vault.list_ids())
    total_notes = len(all_ids)
    
    # Check each note
    for note_id in all_ids:
        note = vault.get(note_id)
        if note is None:
            continue
        
        # Track block labels in this note
        block_labels: dict[str, int] = {}
        
        # Check for duplicate block labels
        for block in note.body.blocks:
            if block.label:
                label_name = block.label.name
                if label_name in block_labels:
                    duplicate_labels += 1
                    findings.append(AuditFinding(
                        note_id=note_id,
                        severity="error",
                        message=f"Duplicate block label: ^{label_name}",
                    ))
                else:
                    block_labels[label_name] = 1
        
        # Check links
        for link in note.body.links:
            total_links += 1
            target_id = link.target.id
            
            # Check if target exists
            if target_id not in all_ids:
                dead_links += 1
                findings.append(AuditFinding(
                    note_id=note_id,
                    severity="error",
                    message=f"Dead link to: {target_id}",
                ))
                continue
            
            # Check anchor if present
            if link.target.anchor:
                target_note = vault.get(target_id)
                if target_note:
                    anchor_found = False
                    
                    if link.target.anchor.kind == "block":
                        # Check for block label
                        label_name = link.target.anchor.value
                        for block in target_note.body.blocks:
                            if block.label and block.label.name == label_name:
                                anchor_found = True
                                break
                    
                    elif link.target.anchor.kind == "heading":
                        # Check for heading slug
                        slug = link.target.anchor.value
                        for block in target_note.body.blocks:
                            if block.heading_slug == slug:
                                anchor_found = True
                                break
                    
                    if not anchor_found:
                        unknown_anchors += 1
                        anchor_repr = (
                            f"^{link.target.anchor.value}"
                            if link.target.anchor.kind == "block"
                            else link.target.anchor.value
                        )
                        findings.append(AuditFinding(
                            note_id=note_id,
                            severity="warning",
                            message=f"Unknown anchor in {target_id}: #{anchor_repr}",
                        ))
        
        # Check for un-migrated links (if strict)
        if strict:
            # Look for wiki links that don't look like IDs
            # Simple heuristic: [[...]] where ... contains spaces or special chars
            wiki_pattern = re.compile(r'\[\[([^\]|#]+)')
            for match in wiki_pattern.finditer(note.body.raw):
                target = match.group(1).strip()
                # Check if target looks like a title (contains space) vs ID (alphanumeric)
                if ' ' in target or not re.match(r'^[a-f0-9_-]+$', target):
                    unmigrated_links += 1
                    severity = "error" if strict else "warning"
                    findings.append(AuditFinding(
                        note_id=note_id,
                        severity=severity,
                        message=f"Un-migrated wiki link: [[{target}]]",
                    ))
            
            # Look for MD links to .md files
            md_pattern = re.compile(r'\]\(([^)]+\.md[^)]*)\)')
            for match in md_pattern.finditer(note.body.raw):
                path = match.group(1)
                if not path.startswith(('http://', 'https://')):
                    unmigrated_links += 1
                    severity = "error" if strict else "warning"
                    findings.append(AuditFinding(
                        note_id=note_id,
                        severity=severity,
                        message=f"Un-migrated MD link: {path}",
                    ))
    
    return AuditReport(
        findings=findings,
        total_notes=total_notes,
        total_links=total_links,
        dead_links=dead_links,
        unknown_anchors=unknown_anchors,
        duplicate_labels=duplicate_labels,
        unmigrated_links=unmigrated_links,
    )
