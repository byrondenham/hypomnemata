"""CLI for hypomnemata - a zettelkasten note-taking system."""

import argparse
import json
import os
import subprocess
import sys
from pathlib import Path
from typing import Any

from .core.meta import MetaBag
from .core.model import Anchor, Note
from .core.slicer import slice_by_anchor
from .export.quartz import QuartzAdapter
from .lint import DeadLinksRule, Finding
from .runtime import build_runtime


def cmd_reindex(args: argparse.Namespace, rt: Any) -> int:
    """Build or repair SQLite index."""
    from .adapters.sqlite_index import SQLiteIndex
    
    if not isinstance(rt.index, SQLiteIndex):
        print("Error: Index is not a SQLiteIndex", file=sys.stderr)
        return 1
    
    full = getattr(args, 'full', False)
    use_hash = getattr(args, 'hash', False)
    
    if not args.quiet:
        print(f"Reindexing vault... (full={full}, hash={use_hash})")
    
    counts = rt.index.rebuild(full=full, use_hash=use_hash)
    
    if not args.quiet:
        print(f"Scanned: {counts['scanned']}")
        print(f"Dirty: {counts['dirty']}")
        print(f"Inserted: {counts['inserted']}")
        print(f"Updated: {counts['updated']}")
        print(f"Removed: {counts['removed']}")
        if counts['failed'] > 0:
            print(f"Failed: {counts['failed']}")
    
    return 0


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
    from .adapters.sqlite_index import SQLiteIndex
    
    # Filter for orphans using DB if available
    if args.orphans:
        if isinstance(rt.index, SQLiteIndex):
            ids = rt.index.orphans()
        else:
            # Fallback to old method
            rt.index.rebuild()
            ids = list(rt.vault.list_ids())
            filtered = []
            for nid in ids:
                if not rt.index.links_in(nid) and not rt.index.links_out(nid):
                    filtered.append(nid)
            ids = filtered
    else:
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
    
    for nid in sorted(ids):
        print(nid)
    
    return 0


def cmd_find(args: argparse.Namespace, rt: Any) -> int:
    """Full-text search."""
    from .adapters.sqlite_index import SQLiteIndex
    
    limit = getattr(args, 'limit', 50)
    snippets = getattr(args, 'snippets', False)
    
    if isinstance(rt.index, SQLiteIndex):
        results = rt.index.search(args.query, limit=limit)
        
        if snippets:
            for nid in results:
                snippet = rt.index.snippet(nid, args.query)
                if snippet:
                    print(f"{nid}\t{snippet}")
                else:
                    print(nid)
        else:
            for nid in results:
                print(nid)
    else:
        # Fallback to old method
        rt.index.rebuild()
        results = rt.index.search(args.query, limit=limit)
        for nid in sorted(results):
            print(nid)
    
    return 0


def cmd_backrefs(args: argparse.Namespace, rt: Any) -> int:
    """Show incoming links with context."""
    context = getattr(args, 'context', 2)
    
    incoming = rt.index.links_in(args.id)
    
    if args.json:
        output = []
        for link in incoming:
            note = rt.vault.get(link.source)
            if note and link.range:
                # Extract context lines around the link
                lines = note.body.raw[:link.range.start].splitlines()
                start_line = max(0, len(lines) - context)
                end_line = len(lines) + context
                context_lines = note.body.raw.splitlines()[start_line:end_line]
                output.append({
                    "source": link.source,
                    "start": link.range.start,
                    "end": link.range.end,
                    "context": "\n".join(context_lines),
                })
        print(json.dumps(output, indent=2))
    else:
        for link in incoming:
            note = rt.vault.get(link.source)
            if note and link.range:
                lines = note.body.raw[:link.range.start].splitlines()
                start_line = max(0, len(lines) - context)
                end_line = len(lines) + context
                context_lines = note.body.raw.splitlines()[start_line:end_line]
                if not args.quiet:
                    print(f"\n{link.source}:")
                for line in context_lines:
                    print(f"  {line}")
    
    return 0


def cmd_graph(args: argparse.Namespace, rt: Any) -> int:
    """Export graph data."""
    from .adapters.sqlite_index import SQLiteIndex
    
    if not isinstance(rt.index, SQLiteIndex):
        print("Error: Graph command requires SQLiteIndex", file=sys.stderr)
        return 1
    
    graph_data = rt.index.graph_data()
    
    if getattr(args, 'dot', False):
        # Output DOT format
        print("digraph vault {")
        print('  rankdir=LR;')
        print('  node [shape=box];')
        for node in graph_data['nodes']:
            label = node['title'] or node['id']
            print(f'  "{node["id"]}" [label="{label}"];')
        for edge in graph_data['edges']:
            print(f'  "{edge["source"]}" -> "{edge["target"]}";')
        print("}")
    else:
        # Output JSON format (default)
        print(json.dumps(graph_data, indent=2))
    
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
                msg = (
                    f"Frontmatter ID '{note.meta['id']}' "
                    f"doesn't match filename '{nid}'"
                )
                all_findings.append((nid, Finding("error", msg)))
    
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


def cmd_yank(args: argparse.Namespace, rt: Any) -> int:
    """Print a slice of a note based on anchor."""
    # Parse ref into id and optional anchor
    ref = args.ref
    anchor = None
    
    if "#" in ref:
        nid, anchor_str = ref.split("#", 1)
        if anchor_str.startswith("^"):
            # Block label
            anchor = Anchor(kind="block", value=anchor_str[1:])
        else:
            # Heading slug
            anchor = Anchor(kind="heading", value=anchor_str)
    else:
        nid = ref
    
    # Get note
    note = rt.vault.get(nid)
    if note is None:
        print(f"Note {nid} not found", file=sys.stderr)
        return 1
    
    # Get slice
    start, end = slice_by_anchor(note, anchor)
    
    if start == end:
        # Empty slice means anchor not found
        if anchor:
            anchor_repr = f"^{anchor.value}" if anchor.kind == "block" else anchor.value
            print(f"Anchor #{anchor_repr} not found in note {nid}", file=sys.stderr)
            return 1
        # Shouldn't happen for no anchor case, but handle it
        return 0
    
    slice_text = note.body.raw[start:end]
    
    # Handle --plain flag for fenced blocks
    if args.plain and slice_text.strip().startswith("```"):
        lines = slice_text.splitlines(keepends=True)
        # Remove first and last lines if they are fence markers
        if len(lines) >= 2 and lines[0].strip().startswith("```") and lines[-1].strip() == "```":
            slice_text = "".join(lines[1:-1])
        elif len(lines) >= 2 and lines[0].strip().startswith("```"):
            # Handle case where last line might not be just ```
            for i in range(len(lines) - 1, 0, -1):
                if lines[i].strip() == "```":
                    slice_text = "".join(lines[1:i])
                    break
    
    # Handle --context flag
    if args.context > 0:
        # Add N lines before and after
        all_lines = note.body.raw.splitlines(keepends=True)
        slice_lines = slice_text.splitlines(keepends=True)
        
        # Find where slice starts in the full text
        slice_start_line = 0
        for i, line in enumerate(all_lines):
            if slice_lines and line == slice_lines[0]:
                slice_start_line = i
                break
        
        start_line = max(0, slice_start_line - args.context)
        end_line = min(len(all_lines), slice_start_line + len(slice_lines) + args.context)
        
        slice_text = "".join(all_lines[start_line:end_line])
    
    print(slice_text, end="")
    return 0


def main() -> None:
    """Main CLI entry point."""
    parser = argparse.ArgumentParser(
        prog="hypo", description="Hypomnemata CLI"
    )
    parser.add_argument(
        "--vault",
        type=Path,
        default=Path("./vault"),
        help="Path to vault directory",
    )
    parser.add_argument(
        "--db",
        type=Path,
        default=None,
        help="Path to SQLite index DB (default: vault/.hypo/index.sqlite)",
    )
    parser.add_argument(
        "-q", "--quiet", action="store_true", help="Minimize output"
    )
    parser.add_argument(
        "--json", action="store_true", help="Machine-readable output"
    )
    
    subparsers = parser.add_subparsers(dest="cmd", required=True)
    
    # id command
    subparsers.add_parser("id", help="Print a new random ID")
    
    # reindex command
    parser_reindex = subparsers.add_parser("reindex", help="Build or repair SQLite index")
    parser_reindex.add_argument(
        "--full", action="store_true", help="Force full rebuild"
    )
    parser_reindex.add_argument(
        "--hash", action="store_true", help="Use SHA256 hash for change detection"
    )
    
    # new command
    parser_new = subparsers.add_parser("new", help="Create a new note")
    parser_new.add_argument(
        "--meta",
        action="append",
        default=[],
        help="Metadata key=value pairs",
    )
    parser_new.add_argument("--title", help="Note title")
    parser_new.add_argument(
        "--edit",
        action="store_true",
        help="Open in $EDITOR after creation",
    )
    
    # open command
    parser_open = subparsers.add_parser(
        "open", help="Print raw Markdown to stdout"
    )
    parser_open.add_argument("id", help="Note ID")
    
    # edit command
    parser_edit = subparsers.add_parser("edit", help="Open in $EDITOR")
    parser_edit.add_argument("id", help="Note ID")
    
    # ls command
    parser_ls = subparsers.add_parser("ls", help="List notes with filters")
    parser_ls.add_argument("--grep", help="Filter by content pattern")
    parser_ls.add_argument(
        "--orphans", action="store_true", help="Show notes with no links"
    )
    
    # find command
    parser_find = subparsers.add_parser("find", help="Full-text search")
    parser_find.add_argument("query", help="Search query")
    parser_find.add_argument(
        "--limit", type=int, default=50, help="Maximum results (default: 50)"
    )
    parser_find.add_argument(
        "--snippets", action="store_true", help="Show snippets with highlights"
    )
    
    # backrefs command
    parser_backrefs = subparsers.add_parser(
        "backrefs", help="Show incoming links with context"
    )
    parser_backrefs.add_argument("id", help="Note ID")
    parser_backrefs.add_argument(
        "--context", type=int, default=2, help="Context lines around link (default: 2)"
    )
    
    # graph command
    parser_graph = subparsers.add_parser("graph", help="Export graph data")
    parser_graph.add_argument(
        "--dot", action="store_true", help="Output in DOT format for Graphviz"
    )
    
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
    
    # yank command
    parser_yank = subparsers.add_parser("yank", help="Print a slice of a note")
    parser_yank.add_argument("ref", help="Note reference: <id> or <id>#<anchor>")
    parser_yank.add_argument(
        "--plain", action="store_true", help="Strip outermost fences for fenced blocks"
    )
    parser_yank.add_argument(
        "--context", type=int, default=0, help="Include N lines before/after (default: 0)"
    )
    
    args = parser.parse_args()
    
    # Build runtime
    rt = build_runtime(args.vault, db_path=args.db)
    
    # Dispatch to command handlers
    handlers = {
        "id": cmd_id,
        "reindex": cmd_reindex,
        "new": cmd_new,
        "open": cmd_open,
        "edit": cmd_edit,
        "ls": cmd_ls,
        "find": cmd_find,
        "backrefs": cmd_backrefs,
        "graph": cmd_graph,
        "lint": cmd_lint,
        "export": cmd_export_quartz,
        "rm": cmd_rm,
        "yank": cmd_yank,
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
