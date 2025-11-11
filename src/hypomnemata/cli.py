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
from .locate import cmd_locate
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
    
    # Sort IDs
    ids = sorted(ids)
    
    # Handle different output formats
    if getattr(args, 'format', None) == 'json':
        # JSON output with titles
        if isinstance(rt.index, SQLiteIndex):
            conn = rt.index._conn()
            try:
                result = []
                for nid in ids:
                    row = conn.execute(
                        "SELECT title FROM notes WHERE id = ?",
                        (nid,)
                    ).fetchone()
                    title = row[0] if row else ""
                    result.append({"id": nid, "title": title})
                print(json.dumps(result, indent=2))
            finally:
                conn.close()
        else:
            # Fallback without titles
            result = [{"id": nid, "title": ""} for nid in ids]
            print(json.dumps(result, indent=2))
    elif getattr(args, 'with_titles', False):
        # Tab-separated output
        if isinstance(rt.index, SQLiteIndex):
            conn = rt.index._conn()
            try:
                for nid in ids:
                    row = conn.execute(
                        "SELECT title FROM notes WHERE id = ?",
                        (nid,)
                    ).fetchone()
                    title = row[0] if row else ""
                    print(f"{nid}\t{title}")
            finally:
                conn.close()
        else:
            # Fallback without titles
            for nid in ids:
                print(f"{nid}\t")
    else:
        # Default: just IDs
        for nid in ids:
            print(nid)
    
    return 0


def cmd_find(args: argparse.Namespace, rt: Any) -> int:
    """Full-text search."""
    from .adapters.sqlite_index import SQLiteIndex
    
    limit = getattr(args, 'limit', 50)
    snippets = getattr(args, 'snippets', False)
    aliases = getattr(args, 'aliases', False)
    fields = getattr(args, 'fields', None)
    
    if isinstance(rt.index, SQLiteIndex):
        results = list(rt.index.search(args.query, limit=limit))
        
        # Add alias matches if requested
        if aliases:
            conn = rt.index._conn()
            try:
                alias_rows = conn.execute(
                    "SELECT DISTINCT note_id FROM kv WHERE key = 'core/alias' AND value LIKE ?",
                    (f"%{args.query}%",)
                ).fetchall()
                
                for row in alias_rows:
                    if row[0] not in results:
                        results.append(row[0])
            finally:
                conn.close()
        
        # Output with fields
        if fields:
            field_list = [f.strip() for f in fields.split(',')]
            conn = rt.index._conn()
            try:
                for nid in results:
                    values = []
                    for field in field_list:
                        if field == 'id':
                            values.append(nid)
                        elif field == 'title':
                            row = conn.execute(
                                "SELECT title FROM notes WHERE id = ?",
                                (nid,)
                            ).fetchone()
                            values.append(row[0] if row else "")
                        else:
                            values.append("")
                    print("\t".join(values))
            finally:
                conn.close()
        elif snippets:
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
    
    # Get assets dir if specified
    assets_dir = None
    if getattr(args, 'assets_dir', None):
        assets_dir = Path(args.assets_dir)
    
    # Get KaTeX auto setting from config or args
    katex_auto = False
    if rt.config.export.quartz:
        katex_auto = rt.config.export.quartz.katex.auto
    
    adapter = QuartzAdapter(
        rt.vault,
        outdir,
        index=rt.index,
        assets_dir=assets_dir,
        katex_auto=katex_auto,
    )
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


def cmd_meta_get(args: argparse.Namespace, rt: Any) -> int:
    """Get metadata values from a note."""
    note = rt.vault.get(args.id)
    if note is None:
        print(f"Note {args.id} not found", file=sys.stderr)
        return 1
    
    if args.keys:
        # Print specific keys
        for key in args.keys:
            if key in note.meta:
                value = note.meta[key]
                if args.json:
                    print(json.dumps({key: value}))
                else:
                    print(f"{key}={value}")
            elif not args.quiet:
                print(f"Key '{key}' not found", file=sys.stderr)
    else:
        # Print all metadata
        if args.json:
            print(json.dumps(dict(note.meta)))
        else:
            for key, value in note.meta.items():
                print(f"{key}={value}")
    
    return 0


def cmd_meta_set(args: argparse.Namespace, rt: Any) -> int:
    """Set metadata values in a note."""
    note = rt.vault.get(args.id)
    if note is None:
        print(f"Note {args.id} not found", file=sys.stderr)
        return 1
    
    # Parse key=value pairs
    for kv in args.pairs:
        if "=" not in kv:
            print(f"Invalid format: {kv}. Expected key=value", file=sys.stderr)
            return 1
        
        key, _, value_str = kv.partition("=")
        key = key.strip()
        value_str = value_str.strip()
        
        # Try to parse value intelligently
        value: Any = value_str
        
        # Check for JSON objects/arrays
        if value_str.startswith("{") or value_str.startswith("["):
            try:
                value = json.loads(value_str)
            except json.JSONDecodeError:
                pass  # Use as string
        # Check for boolean
        elif value_str.lower() in ("true", "false"):
            value = value_str.lower() == "true"
        # Check for numbers
        else:
            try:
                if "." in value_str:
                    value = float(value_str)
                else:
                    value = int(value_str)
            except ValueError:
                pass  # Use as string
        
        note.meta[key] = value
    
    # Save note
    rt.vault.put(note)
    
    if not args.quiet:
        print(f"Updated metadata for {args.id}")
    
    return 0


def cmd_meta_unset(args: argparse.Namespace, rt: Any) -> int:
    """Remove metadata keys from a note."""
    note = rt.vault.get(args.id)
    if note is None:
        print(f"Note {args.id} not found", file=sys.stderr)
        return 1
    
    removed = []
    for key in args.keys:
        if key in note.meta:
            del note.meta[key]
            removed.append(key)
    
    if removed:
        rt.vault.put(note)
        if not args.quiet:
            print(f"Removed keys: {', '.join(removed)}")
    elif not args.quiet:
        print("No keys removed")
    
    return 0


def cmd_meta_show(args: argparse.Namespace, rt: Any) -> int:
    """Pretty-print frontmatter for a note."""
    import yaml
    
    note = rt.vault.get(args.id)
    if note is None:
        print(f"Note {args.id} not found", file=sys.stderr)
        return 1
    
    if note.meta:
        print(yaml.dump(dict(note.meta), sort_keys=False, allow_unicode=True), end="")
    else:
        print("# No metadata")
    
    return 0


def cmd_resolve(args: argparse.Namespace, rt: Any) -> int:
    """Resolve text to note ID via aliases or title."""
    from .adapters.sqlite_index import SQLiteIndex
    
    text = args.text
    
    if not isinstance(rt.index, SQLiteIndex):
        print("Error: Resolve command requires SQLiteIndex", file=sys.stderr)
        return 1
    
    conn = rt.index._conn()
    try:
        # First, check for exact alias match
        alias_rows = conn.execute(
            "SELECT note_id FROM kv WHERE key = 'core/alias' AND value = ?",
            (text,)
        ).fetchall()
        
        if len(alias_rows) == 1:
            # Exact alias match
            print(alias_rows[0][0])
            return 0
        elif len(alias_rows) > 1:
            # Multiple aliases match - ambiguous
            if not args.quiet:
                print(f"Ambiguous: '{text}' matches multiple notes via aliases:", file=sys.stderr)
                for row in alias_rows:
                    note_id = row[0]
                    title_row = conn.execute(
                        "SELECT title FROM notes WHERE id = ?",
                        (note_id,)
                    ).fetchone()
                    title = title_row[0] if title_row else ""
                    print(f"  {note_id}\t{title} (alias)", file=sys.stderr)
            return 2
        
        # Check for exact title match
        title_rows = conn.execute(
            "SELECT id FROM notes WHERE title = ?",
            (text,)
        ).fetchall()
        
        if len(title_rows) == 1:
            # Exact title match
            print(title_rows[0][0])
            return 0
        elif len(title_rows) > 1:
            # Multiple titles match - ambiguous
            if not args.quiet:
                print(f"Ambiguous: '{text}' matches multiple notes via title:", file=sys.stderr)
                for row in title_rows:
                    print(f"  {row[0]}\t{text}", file=sys.stderr)
            return 2
        
        # No exact match - show candidates
        if not args.quiet:
            print(f"No exact match for '{text}'. Candidates:", file=sys.stderr)
            
            # Find similar titles
            similar_titles = conn.execute(
                "SELECT id, title FROM notes WHERE title LIKE ? LIMIT 10",
                (f"%{text}%",)
            ).fetchall()
            
            for note_id, title in similar_titles:
                print(f"  {note_id}\t{title}", file=sys.stderr)
            
            # Find similar aliases
            similar_aliases = conn.execute(
                "SELECT note_id, value FROM kv WHERE key = 'core/alias' AND value LIKE ? LIMIT 10",
                (f"%{text}%",)
            ).fetchall()
            
            for note_id, alias in similar_aliases:
                print(f"  {note_id}\t{alias} (alias)", file=sys.stderr)
        
        return 2  # Ambiguous/not found
    finally:
        conn.close()


def cmd_doctor(args: argparse.Namespace, rt: Any) -> int:
    """Run diagnostics on the vault and index."""
    import random

    from .adapters.sqlite_index import SQLiteIndex
    
    issues = []
    
    # Check vault exists and is writable
    vault_path = rt.vault.storage.root
    if not vault_path.exists():
        print(f"✗ Vault does not exist: {vault_path}")
        issues.append("vault_missing")
    elif not vault_path.is_dir():
        print(f"✗ Vault is not a directory: {vault_path}")
        issues.append("vault_not_dir")
    else:
        print(f"✓ Vault exists: {vault_path}")
        
        # Check if writable
        try:
            test_file = vault_path / ".hypo_test_write"
            test_file.touch()
            test_file.unlink()
            print("✓ Vault is writable")
        except Exception as e:
            print(f"✗ Vault is not writable: {e}")
            issues.append("vault_not_writable")
    
    # Check DB exists and schema is correct
    if isinstance(rt.index, SQLiteIndex):
        db_path = rt.index.db_path
        if not db_path.exists():
            print(f"✗ Database does not exist: {db_path}")
            issues.append("db_missing")
        else:
            print(f"✓ Database exists: {db_path}")
            
            # Check schema version
            conn = rt.index._conn()
            try:
                schema_version = conn.execute(
                    "SELECT value FROM meta WHERE key = 'schema_version'"
                ).fetchone()
                
                if schema_version:
                    print(f"✓ Schema version: {schema_version[0]}")
                else:
                    print("✗ Schema version not found")
                    issues.append("schema_version_missing")
            except Exception as e:
                print(f"✗ Failed to check schema: {e}")
                issues.append("schema_check_failed")
            finally:
                conn.close()
    else:
        print("⚠ Not using SQLiteIndex")
    
    # Sample parse on N random notes
    all_ids = list(rt.vault.list_ids())
    if all_ids:
        sample_size = min(10, len(all_ids))
        sample_ids = random.sample(all_ids, sample_size)
        
        parse_errors = 0
        for nid in sample_ids:
            note = rt.vault.get(nid)
            if note is None:
                parse_errors += 1
        
        if parse_errors == 0:
            print(f"✓ Sampled {sample_size} notes, all parsed successfully")
        else:
            print(f"✗ Failed to parse {parse_errors}/{sample_size} sampled notes")
            issues.append("parse_errors")
    else:
        print("⚠ No notes found in vault")
    
    # Report counts
    if isinstance(rt.index, SQLiteIndex):
        conn = rt.index._conn()
        try:
            note_count = conn.execute("SELECT COUNT(*) FROM notes").fetchone()[0]
            link_count = conn.execute("SELECT COUNT(*) FROM links").fetchone()[0]
            
            # Count orphans (notes with no incoming or outgoing links)
            orphan_count = conn.execute("""
                SELECT COUNT(*) FROM notes
                WHERE id NOT IN (SELECT DISTINCT src FROM links)
                  AND id NOT IN (SELECT DISTINCT dst FROM links)
            """).fetchone()[0]
            
            print("\nCounts:")
            print(f"  Notes: {note_count}")
            print(f"  Links: {link_count}")
            print(f"  Orphans: {orphan_count}")
        finally:
            conn.close()
    
    # Recommendations
    if issues:
        print("\nRecommendations:")
        if "db_missing" in issues or "schema_check_failed" in issues:
            print("  Run: hypo reindex --full")
        if "parse_errors" in issues:
            print("  Check notes for syntax errors")
        return 1
    else:
        print("\n✓ All checks passed")
        return 0


def cmd_watch(args: argparse.Namespace, rt: Any) -> int:
    """Watch vault for changes and incrementally reindex."""
    from .watch import watch_vault
    
    debounce_ms = getattr(args, 'debounce_ms', 150)
    
    return watch_vault(
        vault_path=rt.vault.storage.root,
        index=rt.index,
        debounce_ms=debounce_ms,
        quiet=args.quiet,
        json_output=args.json,
    )


def cmd_serve(args: argparse.Namespace, rt: Any) -> int:
    """Start local JSON API server."""
    try:
        import uvicorn

        from .api.app import create_app, generate_token
    except ImportError as e:
        print(
            "Error: API dependencies not installed. "
            "Install with: pip install hypomnemata[api]",
            file=sys.stderr
        )
        print(f"Details: {e}", file=sys.stderr)
        return 1
    
    # Determine token
    token_arg = getattr(args, 'token', 'auto')
    token = None
    
    if token_arg == 'auto':
        token = generate_token()
        print(f"Generated bearer token: {token}")
        print(f"Use in requests: Authorization: Bearer {token}")
    elif token_arg == 'none':
        print("Warning: Running without authentication. Only use in trusted environments.")
        token = None
    else:
        token = token_arg
    
    # Create app
    enable_cors = getattr(args, 'cors', False)
    openapi = getattr(args, 'openapi', False)
    app = create_app(rt, token=token, enable_cors=enable_cors)
    
    # Enable/disable OpenAPI docs
    if openapi and token:
        # Re-enable docs
        app.docs_url = "/docs"
        app.redoc_url = "/redoc"
    
    # Get host and port
    host = getattr(args, 'host', '127.0.0.1')
    port = getattr(args, 'port', 8765)
    
    print(f"Starting server on http://{host}:{port}")
    if token:
        print(f"Authorization required: Bearer {token}")
    
    # Run server
    uvicorn.run(app, host=host, port=port, log_level="info")
    
    return 0


def cmd_import_plan(args: argparse.Namespace, rt: Any) -> int:
    """Scan source and build import plan."""
    from .import_migrate.plan import build_import_plan, save_plan_csv, save_plan_json
    
    src_dir = Path(args.src).resolve()
    if not src_dir.exists():
        print(f"Source directory does not exist: {src_dir}", file=sys.stderr)
        return 1
    
    # Build plan
    alias_keys = args.alias_keys.split(',') if args.alias_keys else None
    plan = build_import_plan(
        src_dir=src_dir,
        glob_pattern=args.glob,
        id_strategy=args.id_by,
        id_bytes=rt.config.id.bytes,
        title_key=args.title_key,
        alias_keys=alias_keys,
        strict=args.strict,
    )
    
    # Save outputs
    if args.map:
        map_path = Path(args.map)
        save_plan_json(plan, map_path)
        if not args.quiet:
            print(f"Saved plan JSON to: {map_path}")
    
    if args.csv:
        csv_path = Path(args.csv)
        save_plan_csv(plan, csv_path)
        if not args.quiet:
            print(f"Saved plan CSV to: {csv_path}")
    
    # Print summary
    if not args.quiet:
        ok_count = sum(1 for item in plan.items if item.status == "ok")
        conflict_count = sum(1 for item in plan.items if item.status == "conflict")
        error_count = sum(1 for item in plan.items if item.status == "error")
        
        print("\nImport Plan Summary:")
        print(f"  Total items: {len(plan.items)}")
        print(f"  OK: {ok_count}")
        print(f"  Conflicts: {conflict_count}")
        print(f"  Errors: {error_count}")
        
        if plan.conflicts:
            print("\nConflicts detected:")
            for key, paths in plan.conflicts.items():
                print(f"  {key}: {len(paths)} files")
    
    return 1 if plan.conflicts or error_count > 0 else 0


def cmd_import_apply(args: argparse.Namespace, rt: Any) -> int:
    """Execute import based on plan."""
    from .import_migrate.apply import apply_import, save_manifest
    from .import_migrate.plan import build_import_plan, load_plan_json
    
    dst_vault = Path(args.dst_vault).resolve()
    
    # Load or build plan
    if args.plan:
        plan = load_plan_json(Path(args.plan))
    else:
        # Rebuild plan
        src_dir = Path(args.src).resolve()
        if not src_dir.exists():
            print(f"Source directory does not exist: {src_dir}", file=sys.stderr)
            return 1
        
        plan = build_import_plan(
            src_dir=src_dir,
            glob_pattern="**/*.md",
            id_strategy="random",
            id_bytes=rt.config.id.bytes,
        )
    
    # Check for confirmation if not dry-run
    if not args.dry_run and not args.confirm:
        print("Error: --confirm required to execute import", file=sys.stderr)
        return 1
    
    # Execute import
    try:
        manifest = apply_import(
            plan=plan,
            dst_vault=dst_vault,
            operation=args.move if args.move else "copy",
            dry_run=args.dry_run,
            on_conflict=args.on_conflict,
        )
        
        # Save manifest
        if not args.dry_run:
            manifest_dir = dst_vault / ".hypo"
            manifest_dir.mkdir(exist_ok=True)
            manifest_path = manifest_dir / "import-manifest.json"
            save_manifest(manifest, manifest_path)
            
            if not args.quiet:
                print(f"\nImport completed. Manifest saved to: {manifest_path}")
                print(f"  Imported: {len(manifest.entries)} files")
        
        return 0
    except Exception as e:
        print(f"Error during import: {e}", file=sys.stderr)
        return 1


def cmd_import_rollback(args: argparse.Namespace, rt: Any) -> int:
    """Rollback import operations."""
    from .import_migrate.rollback import rollback_from_file
    
    manifest_path = Path(args.manifest)
    if not manifest_path.exists():
        print(f"Manifest not found: {manifest_path}", file=sys.stderr)
        return 1
    
    # Check for confirmation if not dry-run
    if not args.dry_run and not args.confirm:
        print("Error: --confirm required to execute rollback", file=sys.stderr)
        return 1
    
    try:
        rollback_from_file(manifest_path, dry_run=args.dry_run)
        if not args.quiet:
            print("Rollback completed.")
        return 0
    except Exception as e:
        print(f"Error during rollback: {e}", file=sys.stderr)
        return 1


def cmd_migrate_links(args: argparse.Namespace, rt: Any) -> int:
    """Migrate wiki/MD links to ID-based format."""
    from .adapters.sqlite_index import SQLiteIndex
    from .import_migrate.migrate import apply_migration, migrate_file_links
    
    if not isinstance(rt.index, SQLiteIndex):
        print("Error: Migrate requires SQLiteIndex", file=sys.stderr)
        return 1
    
    # Check for confirmation if not dry-run
    if not args.dry_run and not args.confirm:
        print("Error: --confirm required to execute migration", file=sys.stderr)
        return 1
    
    vault_path = rt.vault.storage.root
    
    # Ensure index is up to date
    if not args.quiet:
        print("Updating index...")
    rt.index.rebuild()
    
    # Migrate all files in vault
    total_files = 0
    total_changes = 0
    total_errors = 0
    
    for note_id in rt.vault.list_ids():
        file_path = vault_path / f"{note_id}.md"
        if not file_path.exists():
            continue
        
        total_files += 1
        
        result = migrate_file_links(
            file_path=file_path,
            vault_path=vault_path,
            index=rt.index,
            from_format=args.from_format,
            resolver_mode=args.resolver,
            prefer=args.prefer,
        )
        
        if result.errors:
            total_errors += len(result.errors)
            if not args.quiet:
                print(f"\n{file_path}:")
                for error in result.errors:
                    print(f"  ! {error}")
        
        if result.changes > 0:
            total_changes += result.changes
            apply_migration(result, dry_run=args.dry_run)
    
    # Print summary
    if not args.quiet:
        print("\nMigration Summary:")
        print(f"  Files processed: {total_files}")
        print(f"  Links changed: {total_changes}")
        print(f"  Errors: {total_errors}")
    
    return 1 if total_errors > 0 else 0


def cmd_audit_links(args: argparse.Namespace, rt: Any) -> int:
    """Audit vault for link integrity."""
    from .adapters.sqlite_index import SQLiteIndex
    from .import_migrate.audit import audit_vault
    
    if not isinstance(rt.index, SQLiteIndex):
        print("Error: Audit requires SQLiteIndex", file=sys.stderr)
        return 1
    
    # Ensure index is up to date
    rt.index.rebuild()
    
    # Run audit
    report = audit_vault(rt.vault, rt.index, strict=args.strict)
    
    # Print results
    if args.json:
        output = {
            "total_notes": report.total_notes,
            "total_links": report.total_links,
            "dead_links": report.dead_links,
            "unknown_anchors": report.unknown_anchors,
            "duplicate_labels": report.duplicate_labels,
            "unmigrated_links": report.unmigrated_links,
            "findings": [
                {
                    "note_id": f.note_id,
                    "severity": f.severity,
                    "message": f.message,
                }
                for f in report.findings
            ],
        }
        print(json.dumps(output, indent=2))
    else:
        print("Audit Results:")
        print(f"  Total notes: {report.total_notes}")
        print(f"  Total links: {report.total_links}")
        print(f"  Dead links: {report.dead_links}")
        print(f"  Unknown anchors: {report.unknown_anchors}")
        print(f"  Duplicate labels: {report.duplicate_labels}")
        if args.strict:
            print(f"  Un-migrated links: {report.unmigrated_links}")
        
        if report.findings:
            print("\nFindings:")
            for finding in report.findings:
                print(f"  [{finding.severity}] {finding.note_id}: {finding.message}")
    
    return 1 if report.has_errors else 0


def main() -> None:
    """Main CLI entry point."""
    parser = argparse.ArgumentParser(
        prog="hypo", description="Hypomnemata CLI"
    )
    parser.add_argument(
        "--config",
        type=Path,
        default=None,
        help="Path to config file (default: search cwd/hypo.toml, vault/hypo.toml)",
    )
    parser.add_argument(
        "--vault",
        type=Path,
        default=None,
        help="Path to vault directory (overrides config)",
    )
    parser.add_argument(
        "--db",
        type=Path,
        default=None,
        help="Path to SQLite index DB (overrides config)",
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
    parser_ls.add_argument(
        "--with-titles", dest="with_titles", action="store_true",
        help="Print id and title (tab-separated)"
    )
    parser_ls.add_argument(
        "--format", choices=["json"], help="Output format (json)"
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
    parser_find.add_argument(
        "--aliases", action="store_true", help="Include alias matches"
    )
    parser_find.add_argument(
        "--fields", help="Comma-separated fields to display (e.g., id,title)"
    )
    
    # resolve command
    parser_resolve = subparsers.add_parser("resolve", help="Resolve text to note ID")
    parser_resolve.add_argument("text", help="Text to resolve (alias or title)")
    
    # doctor command
    subparsers.add_parser("doctor", help="Run diagnostics on vault and index")
    
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
    parser_quartz.add_argument(
        "--assets-dir",
        dest="assets_dir",
        help="Copy assets from this directory to output/assets/",
    )
    
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
    
    # meta command
    parser_meta = subparsers.add_parser("meta", help="Manage note metadata")
    meta_sub = parser_meta.add_subparsers(dest="meta_cmd", required=True)
    
    parser_meta_get = meta_sub.add_parser("get", help="Get metadata values")
    parser_meta_get.add_argument("id", help="Note ID")
    parser_meta_get.add_argument("--keys", nargs="+", help="Specific keys to retrieve")
    
    parser_meta_set = meta_sub.add_parser("set", help="Set metadata values")
    parser_meta_set.add_argument("id", help="Note ID")
    parser_meta_set.add_argument("pairs", nargs="+", help="key=value pairs")
    
    parser_meta_unset = meta_sub.add_parser("unset", help="Remove metadata keys")
    parser_meta_unset.add_argument("id", help="Note ID")
    parser_meta_unset.add_argument("keys", nargs="+", help="Keys to remove")
    
    parser_meta_show = meta_sub.add_parser("show", help="Pretty-print frontmatter")
    parser_meta_show.add_argument("id", help="Note ID")
    
    # watch command
    parser_watch = subparsers.add_parser("watch", help="Watch vault for changes")
    parser_watch.add_argument(
        "--debounce-ms", type=int, default=150,
        help="Debounce window in milliseconds (default: 150)"
    )
    
    # locate command
    parser_locate = subparsers.add_parser("locate", help="Get precise location of note or anchor")
    parser_locate.add_argument("ref", help="Note reference: <id> or <id>#<anchor>")
    parser_locate.add_argument(
        "--format", choices=["json", "tsv"], default="json",
        help="Output format (default: json)"
    )
    parser_locate.add_argument(
        "--context", type=int, default=0,
        help="Context lines (reserved for future use)"
    )
    
    # serve command
    parser_serve = subparsers.add_parser("serve", help="Start local JSON API server")
    parser_serve.add_argument(
        "--host", default="127.0.0.1",
        help="Host to bind to (default: 127.0.0.1)"
    )
    parser_serve.add_argument(
        "--port", type=int, default=8765,
        help="Port to bind to (default: 8765)"
    )
    parser_serve.add_argument(
        "--token", default="auto",
        help="Bearer token (auto|<string>|none, default: auto)"
    )
    parser_serve.add_argument(
        "--cors", action="store_true",
        help="Enable CORS (default: false)"
    )
    parser_serve.add_argument(
        "--openapi", action="store_true",
        help="Enable OpenAPI docs at /docs (default: false)"
    )
    
    # import command
    parser_import = subparsers.add_parser("import", help="Import Markdown notes")
    import_sub = parser_import.add_subparsers(dest="import_cmd", required=True)
    
    # import plan
    parser_import_plan = import_sub.add_parser("plan", help="Scan source and build import plan")
    parser_import_plan.add_argument("src", help="Source directory to scan")
    parser_import_plan.add_argument(
        "--glob", default="**/*.md",
        help="File glob pattern (default: **/*.md)"
    )
    parser_import_plan.add_argument(
        "--map", help="Output path for plan JSON file"
    )
    parser_import_plan.add_argument(
        "--csv", help="Output path for plan CSV file"
    )
    parser_import_plan.add_argument(
        "--id-by", choices=["random", "hash", "slug"], default="random",
        help="ID generation strategy (default: random)"
    )
    parser_import_plan.add_argument(
        "--title-key", default="core/title",
        help="Frontmatter key for title (default: core/title)"
    )
    parser_import_plan.add_argument(
        "--alias-keys", default=None,
        help="Comma-separated frontmatter keys for aliases (default: core/aliases,aliases)"
    )
    parser_import_plan.add_argument(
        "--strict", action="store_true",
        help="Fail on any conflicts"
    )
    
    # import apply
    parser_import_apply = import_sub.add_parser("apply", help="Execute import")
    parser_import_apply.add_argument("src", help="Source directory")
    parser_import_apply.add_argument("dst_vault", help="Destination vault directory")
    parser_import_apply.add_argument(
        "--plan", help="Path to plan JSON file (optional)"
    )
    parser_import_apply.add_argument(
        "--move", action="store_true",
        help="Move files instead of copy"
    )
    parser_import_apply.add_argument(
        "--dry-run", action="store_true",
        help="Print changes without writing"
    )
    parser_import_apply.add_argument(
        "--confirm", action="store_true",
        help="Required to proceed (unless dry-run)"
    )
    parser_import_apply.add_argument(
        "--on-conflict", choices=["skip", "new-id", "fail"], default="fail",
        help="How to handle existing files (default: fail)"
    )
    
    # import rollback
    parser_import_rollback = import_sub.add_parser("rollback", help="Rollback import")
    parser_import_rollback.add_argument(
        "--manifest", default=".hypo/import-manifest.json",
        help="Path to manifest file (default: .hypo/import-manifest.json)"
    )
    parser_import_rollback.add_argument(
        "--dry-run", action="store_true",
        help="Print changes without writing"
    )
    parser_import_rollback.add_argument(
        "--confirm", action="store_true",
        help="Required to proceed (unless dry-run)"
    )
    
    # migrate command
    parser_migrate = subparsers.add_parser("migrate", help="Migrate links")
    migrate_sub = parser_migrate.add_subparsers(dest="migrate_cmd", required=True)
    
    # migrate links
    parser_migrate_links = migrate_sub.add_parser("links", help="Migrate wiki/MD links to IDs")
    parser_migrate_links.add_argument(
        "--dry-run", action="store_true",
        help="Print unified diff without writing"
    )
    parser_migrate_links.add_argument(
        "--confirm", action="store_true",
        help="Required to proceed (unless dry-run)"
    )
    parser_migrate_links.add_argument(
        "--from", dest="from_format", choices=["wiki", "md", "mixed"], default="mixed",
        help="Source link format (default: mixed)"
    )
    parser_migrate_links.add_argument(
        "--resolver", choices=["title", "alias", "both"], default="both",
        help="Resolution strategy (default: both)"
    )
    parser_migrate_links.add_argument(
        "--prefer", choices=["alias", "title"], default="alias",
        help="Preference when both match (default: alias)"
    )
    
    # audit command
    parser_audit = subparsers.add_parser("audit", help="Audit vault integrity")
    audit_sub = parser_audit.add_subparsers(dest="audit_cmd", required=True)
    
    # audit links
    parser_audit_links = audit_sub.add_parser("links", help="Audit link integrity")
    parser_audit_links.add_argument(
        "--strict", action="store_true",
        help="Treat un-migrated links as errors"
    )
    
    args = parser.parse_args()
    
    # Build runtime
    rt = build_runtime(
        vault_path=args.vault,
        db_path=args.db,
        config_path=args.config,
    )
    
    # Dispatch to command handlers
    handlers = {
        "id": cmd_id,
        "reindex": cmd_reindex,
        "new": cmd_new,
        "open": cmd_open,
        "edit": cmd_edit,
        "ls": cmd_ls,
        "find": cmd_find,
        "resolve": cmd_resolve,
        "doctor": cmd_doctor,
        "backrefs": cmd_backrefs,
        "graph": cmd_graph,
        "lint": cmd_lint,
        "export": cmd_export_quartz,
        "rm": cmd_rm,
        "yank": cmd_yank,
        "watch": cmd_watch,
        "locate": cmd_locate,
        "serve": cmd_serve,
    }
    
    # Handle meta subcommand
    if args.cmd == "meta":
        meta_handlers = {
            "get": cmd_meta_get,
            "set": cmd_meta_set,
            "unset": cmd_meta_unset,
            "show": cmd_meta_show,
        }
        handler = meta_handlers.get(args.meta_cmd)
    # Handle import subcommand
    elif args.cmd == "import":
        import_handlers = {
            "plan": cmd_import_plan,
            "apply": cmd_import_apply,
            "rollback": cmd_import_rollback,
        }
        handler = import_handlers.get(args.import_cmd)
    # Handle migrate subcommand
    elif args.cmd == "migrate":
        migrate_handlers = {
            "links": cmd_migrate_links,
        }
        handler = migrate_handlers.get(args.migrate_cmd)
    # Handle audit subcommand
    elif args.cmd == "audit":
        audit_handlers = {
            "links": cmd_audit_links,
        }
        handler = audit_handlers.get(args.audit_cmd)
    else:
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
