"""CLI for hypomnemata - a zettelkasten note-taking system."""

import argparse
import json
import os
import subprocess
import sys
from pathlib import Path
from typing import Any

from .runtime import build_runtime
from .core.meta import MetaBag
from .core.model import Note
from .lint import DeadLinksRule, Finding
from .export.quartz import QuartzAdapter


def cmd_id(args: argparse.Namespace, rt: Any) -> int:
    """Print a new random ID."""
    print(rt.idgen.new_id())
    return 0


def cmd_new(args: argparse.Namespace, rt: Any) -> int:
    """Create a new note."""
    nid = rt.idgen.new_id()
    
    # Build metadata from args
    mb = MetaBag({"id": nid})
    if args.title:
        mb["title"] = args.title
    
    for kv in args.meta:
        k, _, val = kv.partition("=")
        mb[k.strip()] = val.strip()
    
    # Create initial body
    title_line = f"# {args.title}\n\n" if args.title else "# \n\n"
    body = rt.vault.parser.parse(title_line, nid)
    
    # Save note
    note = Note(id=nid, meta=mb, body=body)
    rt.vault.put(note)
    
    if not args.quiet:
        print(nid)
    
    # Open in editor if requested
    if args.edit:
        editor = os.environ.get("EDITOR", "vi")
        filepath = rt.vault.storage._path(nid)
        subprocess.run([editor, str(filepath)])
    
    return 0


def cmd_open(args: argparse.Namespace, rt: Any) -> int:
    """Print raw Markdown to stdout."""
    note = rt.vault.get(args.id)
    if note is None:
        print(f"Note {args.id} not found", file=sys.stderr)
        return 1
    print(note.body.raw)
    return 0


def cmd_edit(args: argparse.Namespace, rt: Any) -> int:
    """Open note in $EDITOR."""
    if rt.vault.get(args.id) is None:
        print(f"Note {args.id} not found", file=sys.stderr)
        return 1
    
    editor = os.environ.get("EDITOR", "vi")
    filepath = rt.vault.storage._path(args.id)
    subprocess.run([editor, str(filepath)])
    return 0


def cmd_ls(args: argparse.Namespace, rt: Any) -> int:
    """List notes with optional filters."""
    ids = list(rt.vault.list_ids())
    
    # Filter by grep pattern
    if args.grep:
        pattern = args.grep.lower()
        filtered = []
        for nid in ids:
            note = rt.vault.get(nid)
            if note and pattern in note.body.raw.lower():
                filtered.append(nid)
        ids = filtered
    
    # Filter for orphans
    if args.orphans:
        rt.index.rebuild()
        filtered = []
        for nid in ids:
            # A note is an orphan if it has no incoming or outgoing links
            if not rt.index.links_in(nid) and not rt.index.links_out(nid):
                filtered.append(nid)
        ids = filtered
    
    for nid in sorted(ids):
        print(nid)
    
    return 0


def cmd_find(args: argparse.Namespace, rt: Any) -> int:
    """Full-text search."""
    rt.index.rebuild()
    results = rt.index.search(args.query)
    for nid in sorted(results):
        print(nid)
    return 0


def cmd_backrefs(args: argparse.Namespace, rt: Any) -> int:
    """Show incoming links with context."""
    rt.index.rebuild()
    incoming = rt.index.links_in(args.id)
    
    if args.json:
        output = []
        for link in incoming:
            note = rt.vault.get(link.source)
            if note and link.range:
                # Extract 2-3 lines of context around the link
                lines = note.body.raw[:link.range.start].splitlines()
                start_line = max(0, len(lines) - 2)
                context_lines = note.body.raw.splitlines()[start_line:start_line + 3]
                output.append({
                    "source": link.source,
                    "context": "\n".join(context_lines),
                })
        print(json.dumps(output, indent=2))
    else:
        for link in incoming:
            note = rt.vault.get(link.source)
            if note and link.range:
                lines = note.body.raw[:link.range.start].splitlines()
                start_line = max(0, len(lines) - 2)
                context_lines = note.body.raw.splitlines()[start_line:start_line + 3]
                if not args.quiet:
                    print(f"\n{link.source}:")
                for line in context_lines:
                    print(f"  {line}")
    
    return 0


def cmd_lint(args: argparse.Namespace, rt: Any) -> int:
    """Validate links and frontmatter."""
    rt.index.rebuild()
    rule = DeadLinksRule()
    
    all_findings: list[tuple[str, Finding]] = []
    for nid in rt.vault.list_ids():
        note = rt.vault.get(nid)
        if note:
            findings = rule.check(note, rt.resolver, rt.index)
            for f in findings:
                all_findings.append((nid, f))
            
            # Check frontmatter ID mismatch
            if "id" in note.meta and note.meta["id"] != nid:
                all_findings.append((
                    nid,
                    Finding("error", f"Frontmatter ID '{note.meta['id']}' doesn't match filename '{nid}'")
                ))
    
    if args.json:
        output = [
            {
                "note_id": nid,
                "severity": f.severity,
                "message": f.message,
                "range": {"start": f.range.start, "end": f.range.end} if f.range else None,
            }
            for nid, f in all_findings
        ]
        print(json.dumps(output, indent=2))
    else:
        for nid, f in all_findings:
            if not args.quiet:
                print(f"{nid}: [{f.severity}] {f.message}")
    
    return 1 if any(f.severity == "error" for _, f in all_findings) else 0


def cmd_export_quartz(args: argparse.Namespace, rt: Any) -> int:
    """Export to Quartz format with graph.json."""
    outdir = Path(args.outdir)
    adapter = QuartzAdapter(rt.vault, outdir)
    adapter.export_all()
    if not args.quiet:
        print(f"Exported to {outdir}")
    return 0


def cmd_rm(args: argparse.Namespace, rt: Any) -> int:
    """Delete/trash a note."""
    if rt.vault.get(args.id) is None:
        print(f"Note {args.id} not found", file=sys.stderr)
        return 1
    
    # Confirm unless --yes
    if not args.yes:
        response = input(f"Delete note {args.id}? [y/N] ")
        if response.lower() not in ("y", "yes"):
            print("Aborted")
            return 0
    
    rt.vault.storage.delete_raw(args.id)
    if not args.quiet:
        print(f"Deleted {args.id}")
    return 0


def main() -> None:
    """Main CLI entry point."""
    parser = argparse.ArgumentParser(prog="hypo", description="Hypomnemata CLI")
    parser.add_argument("--vault", type=Path, default=Path("./vault"), help="Path to vault directory")
    parser.add_argument("-q", "--quiet", action="store_true", help="Minimize output")
    parser.add_argument("--json", action="store_true", help="Machine-readable output")
    
    subparsers = parser.add_subparsers(dest="cmd", required=True)
    
    # id command
    subparsers.add_parser("id", help="Print a new random ID")
    
    # new command
    parser_new = subparsers.add_parser("new", help="Create a new note")
    parser_new.add_argument("--meta", action="append", default=[], help="Metadata key=value pairs")
    parser_new.add_argument("--title", help="Note title")
    parser_new.add_argument("--edit", action="store_true", help="Open in $EDITOR after creation")
    
    # open command
    parser_open = subparsers.add_parser("open", help="Print raw Markdown to stdout")
    parser_open.add_argument("id", help="Note ID")
    
    # edit command
    parser_edit = subparsers.add_parser("edit", help="Open in $EDITOR")
    parser_edit.add_argument("id", help="Note ID")
    
    # ls command
    parser_ls = subparsers.add_parser("ls", help="List notes with filters")
    parser_ls.add_argument("--grep", help="Filter by content pattern")
    parser_ls.add_argument("--orphans", action="store_true", help="Show notes with no links")
    
    # find command
    parser_find = subparsers.add_parser("find", help="Full-text search")
    parser_find.add_argument("query", help="Search query")
    
    # backrefs command
    parser_backrefs = subparsers.add_parser("backrefs", help="Show incoming links with context")
    parser_backrefs.add_argument("id", help="Note ID")
    
    # lint command
    subparsers.add_parser("lint", help="Validate links and frontmatter")
    
    # export command
    parser_export = subparsers.add_parser("export", help="Export vault")
    export_sub = parser_export.add_subparsers(dest="export_type", required=True)
    parser_quartz = export_sub.add_parser("quartz", help="Export to Quartz format")
    parser_quartz.add_argument("outdir", help="Output directory")
    
    # rm command
    parser_rm = subparsers.add_parser("rm", help="Delete/trash a note")
    parser_rm.add_argument("id", help="Note ID")
    parser_rm.add_argument("--yes", action="store_true", help="Skip confirmation")
    
    args = parser.parse_args()
    
    # Build runtime
    rt = build_runtime(args.vault)
    
    # Dispatch to command handlers
    handlers = {
        "id": cmd_id,
        "new": cmd_new,
        "open": cmd_open,
        "edit": cmd_edit,
        "ls": cmd_ls,
        "find": cmd_find,
        "backrefs": cmd_backrefs,
        "lint": cmd_lint,
        "export": cmd_export_quartz,
        "rm": cmd_rm,
    }
    
    handler = handlers.get(args.cmd)
    if handler:
        try:
            exit_code = handler(args, rt)
            sys.exit(exit_code)
        except Exception as e:
            print(f"Error: {e}", file=sys.stderr)
            sys.exit(1)
    else:
        print(f"Unknown command: {args.cmd}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
