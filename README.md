# Hypomnemata

A zettelkasten note-taking system with flat storage, random IDs, wiki-style links, and transclusion support.

## Features

- **ID-based linking**: Notes use random hex IDs (`abc123def456`) for stable references
- **Wiki-style links**: `[[note-id]]` or `[[note-id|Title]]`
- **Transclusion**: `![[note-id]]` to embed content from other notes
- **Slice-based transclusion**: `![[note-id#heading]]` or `![[note-id#^label]]`
- **Full-text search**: SQLite FTS5 index for fast search
- **Metadata support**: Rich metadata with namespaced keys
- **Aliases**: Reference notes by memorable names
- **Quartz export**: Export to Quartz static site format
- **CLI-first**: Full-featured command-line interface

## Quick Start

```bash
# Install
pip install -e .

# Create a note
hypo new --title "My First Note"
# => abc123def456

# Edit it
hypo edit abc123def456

# Search
hypo find "search term"

# List with titles
hypo ls --with-titles
```

## Configuration

Optional `hypo.toml` file for default settings:

```toml
[vault]
root = "vault"

[id]
bytes = 6

[export.quartz]
out = "site"
katex = { auto = true }
```

## Core Concepts

### Notes

Each note is a Markdown file named `{id}.md` with optional YAML frontmatter:

```markdown
---
id: abc123def456
core/title: My Note Title
core/aliases:
  - Quick Reference
  - QR
---

# My Note Title

Content here with [[other-note|links]].
```

### Metadata

Metadata uses namespaced keys for organization:

- `core/title`: Display title for the note
- `core/aliases`: Alternative names for reference
- `user/*`: User-defined metadata (tags, type, etc.)

```bash
hypo meta set abc123 core/title="Research Notes"
hypo meta set abc123 user/tags='["research","important"]'
```

### Links and Transclusion

- `[[note-id]]` - Basic link
- `[[note-id|Display Text]]` - Link with custom text
- `![[note-id]]` - Embed entire note
- `![[note-id#heading]]` - Embed section by heading slug
- `![[note-id#^label]]` - Embed block by label

### Aliases

Reference notes by memorable names instead of IDs:

```bash
# Set aliases
hypo meta set abc123 core/aliases='["Weekly Review","WR"]'
hypo reindex

# Resolve alias to ID
hypo resolve "Weekly Review"
# => abc123
```

## Commands

### Core Commands

- `hypo id` - Generate a new random ID
- `hypo new --title "Title"` - Create a new note
- `hypo edit <id>` - Open note in $EDITOR
- `hypo open <id>` - Print note to stdout
- `hypo ls` - List all notes
- `hypo find <query>` - Full-text search

### Metadata Commands

- `hypo meta get <id>` - Show all metadata
- `hypo meta set <id> key=value` - Set metadata
- `hypo meta unset <id> key` - Remove metadata
- `hypo meta show <id>` - Pretty-print frontmatter

### Discovery Commands

- `hypo resolve <text>` - Resolve alias/title to ID
- `hypo backrefs <id>` - Show incoming links
- `hypo graph` - Export graph data
- `hypo doctor` - Run vault diagnostics

### Maintenance Commands

- `hypo reindex` - Rebuild search index
- `hypo lint` - Check for broken links
- `hypo rm <id>` - Delete a note

### Export Commands

- `hypo export quartz <outdir>` - Export to Quartz format

## CLI Enhancements

### List with Titles

```bash
# Tab-separated
hypo ls --with-titles
abc123My Note Title

# JSON format
hypo ls --format json
[{"id": "abc123", "title": "My Note Title"}]
```

### Enhanced Search

```bash
# Include aliases
hypo find "term" --aliases

# Show snippets
hypo find "term" --snippets

# Custom fields
hypo find "term" --fields id,title
```

### Diagnostics

```bash
hypo doctor
# ✓ Vault exists
# ✓ Database valid
# ✓ Schema version: 2
# Counts: Notes: 42, Links: 127, Orphans: 3
```

## Export to Quartz

```bash
# Basic export
hypo export quartz ./site

# With assets
hypo export quartz ./site --assets-dir vault/assets

# Notes include titles as H1
# Math detection adds .katex flag
# Better error messages for missing transclusions
```

## Documentation

See [CLI_DEMO.md](CLI_DEMO.md) for comprehensive examples and usage.

## Design Principles

1. **Flat files**: Notes are plain Markdown files
2. **ID-based**: Stable references even if titles change
3. **No magic**: Simple, predictable behavior
4. **CLI-first**: Full functionality from command line
5. **Scriptable**: JSON output for automation

## Development

```bash
# Install dev dependencies
pip install -e ".[dev]"

# Run tests
pytest

# Lint
ruff check src tests

# Type check
mypy src
```

## License

MIT
