# Hypomnemata CLI Demonstration

This document demonstrates all commands in the hypomnemata CLI.

## Installation

```bash
pip install -e ".[dev]"
```

## Basic Usage

### 1. Generate a new ID
```bash
$ hypo id
dd2f87043f28
```

### 2. Create a new note
```bash
$ hypo new --title "My First Note" --meta "author=John Doe" --meta "tags=example"
abc123def456

$ hypo new --title "Meeting Notes" --edit  # Opens in $EDITOR
def456abc789
```

### 3. List all notes
```bash
$ hypo --vault examples/vault ls
abcd1234
beta5678
delta4567
gamma9abc
```

### 4. Search notes by content
```bash
$ hypo --vault examples/vault ls --grep "alpha"
abcd1234
beta5678

$ hypo --vault examples/vault find "Gamma"
abcd1234
beta5678
gamma9abc
```

### 5. View a note
```bash
$ hypo --vault examples/vault open abcd1234
# Alpha

This is the first note. It links to [[beta5678|Beta]] and [[gamma9abc]].

Some content here about alpha topics.
```

### 6. Edit a note
```bash
$ hypo --vault examples/vault edit abcd1234
# Opens in $EDITOR (vi by default, or $EDITOR environment variable)
```

### 7. Find incoming links (backreferences)
```bash
$ hypo --vault examples/vault backrefs abcd1234

delta4567:
  
  It also links to [[abcd1234]].

beta5678:
  
  This note references [[abcd1234|Alpha]] and includes a transclusion:

$ hypo --vault examples/vault --json backrefs abcd1234
[
  {
    "source": "delta4567",
    "context": "\nIt also links to [[abcd1234]]."
  },
  {
    "source": "beta5678",
    "context": "\nThis note references [[abcd1234|Alpha]] and includes a transclusion:\n"
  }
]
```

### 8. Lint your vault for broken links
```bash
$ hypo --vault examples/vault lint
delta4567: [error] Unknown note id missing123

$ echo $?
1  # Exit code 1 indicates errors were found

$ hypo --vault examples/vault --json lint
[
  {
    "note_id": "delta4567",
    "severity": "error",
    "message": "Unknown note id missing123",
    "range": {
      "start": 40,
      "end": 54
    }
  }
]
```

### 9. Export to Quartz format
```bash
$ hypo --vault examples/vault export quartz ./site
Exported to ./site

$ tree ./site
./site
├── abcd1234
│   └── index.md
├── beta5678
│   └── index.md
├── delta4567
│   └── index.md
├── gamma9abc
│   └── index.md
└── graph.json

$ cat ./site/abcd1234/index.md
# Alpha

This is the first note. It links to [Beta](/beta5678/) and [gamma9abc](/gamma9abc/).

Some content here about alpha topics.

$ cat ./site/graph.json
{
  "nodes": [
    {"id": "gamma9abc"},
    {"id": "delta4567"},
    {"id": "beta5678"},
    {"id": "abcd1234"}
  ],
  "edges": [
    {"source": "delta4567", "target": "missing123"},
    {"source": "delta4567", "target": "abcd1234"},
    {"source": "beta5678", "target": "abcd1234"},
    {"source": "abcd1234", "target": "beta5678"},
    {"source": "abcd1234", "target": "gamma9abc"}
  ]
}
```

### 10. Delete a note
```bash
$ hypo rm delta4567
Delete note delta4567? [y/N] y
Deleted delta4567

$ hypo rm beta5678 --yes  # Skip confirmation
Deleted beta5678
```

## Global Flags

### Custom vault location
```bash
$ hypo --vault ~/my-notes ls
$ hypo --vault /path/to/vault new --title "Note"
```

### Quiet mode (minimal output)
```bash
$ hypo --quiet new --title "Silent Note"
abc123def456
# Only outputs the ID, no other messages

$ hypo --vault examples/vault --quiet ls
abcd1234
beta5678
delta4567
gamma9abc
```

### JSON output
```bash
$ hypo --vault examples/vault --json lint
$ hypo --vault examples/vault --json backrefs abcd1234
```

## Advanced Examples

### Create a note with complex metadata
```bash
$ hypo new \
  --title "Literature Review: Distributed Systems" \
  --meta "type=research" \
  --meta "author=Alice" \
  --meta "date=2024-01-15" \
  --meta "tags=distributed-systems,consensus,raft"
```

### Find orphaned notes (no incoming or outgoing links)
```bash
$ hypo ls --orphans
# Shows notes that aren't connected to anything
```

### Search and filter workflow
```bash
# Find all notes mentioning "quantum"
$ hypo find quantum

# Filter by content pattern
$ hypo ls --grep "TODO"

# Combine with other tools
$ hypo ls | xargs -I {} hypo open {}
```

### Export and deploy to Quartz
```bash
$ hypo export quartz ~/quartz-site/content
$ cd ~/quartz-site
$ npx quartz build
```

## Configuration

Hypomnemata supports optional configuration via `hypo.toml` to avoid repeating command-line flags.

### Config File Location

The config file is searched in this order:
1. Path specified with `--config`
2. `./hypo.toml` in current directory
3. `vault/hypo.toml` in vault directory

### Example Configuration

```toml
[vault]
root = "vault"
db = ".hypo/index.sqlite"

[id]
bytes = 6  # 12 hex characters

[export.quartz]
out = "site"
katex = { auto = true }

[ui]
colors = true
```

CLI flags always override config values:
```bash
# Uses vault from config
$ hypo ls

# Overrides config vault setting
$ hypo --vault ~/other-vault ls
```

## Metadata Management

Hypomnemata supports rich metadata via the `hypo meta` commands.

### Set Metadata

```bash
# Set single values
$ hypo meta set abc123 core/title="My Custom Title"

# Set multiple values
$ hypo meta set abc123 \
  core/title="Research Notes" \
  user/tags='["research","important"]' \
  user/difficulty=3

# Supported types: strings, numbers, booleans, JSON objects/arrays
$ hypo meta set abc123 \
  user/completed=true \
  user/rating=4.5 \
  user/metadata='{"author": "Jane", "year": 2024}'
```

### Get Metadata

```bash
# Get all metadata
$ hypo meta get abc123
id=abc123
core/title=My Custom Title
user/tags=["research", "important"]

# Get specific keys
$ hypo meta get abc123 --keys core/title user/tags
core/title=My Custom Title
user/tags=["research", "important"]

# JSON output
$ hypo meta get abc123 --json
{
  "id": "abc123",
  "core/title": "My Custom Title",
  "user/tags": ["research", "important"]
}
```

### Show Frontmatter

```bash
# Pretty-print YAML frontmatter
$ hypo meta show abc123
id: abc123
core/title: My Custom Title
core/aliases:
- First Alias
- Second Alias
user/tags:
- research
- important
```

### Remove Metadata

```bash
# Remove one or more keys
$ hypo meta unset abc123 user/tags user/difficulty
Removed keys: user/tags, user/difficulty
```

## Aliases

Aliases allow you to reference notes by memorable names instead of IDs.

### Set Aliases

```bash
$ hypo meta set abc123 core/aliases='["Quick Reference","QR Guide"]'

# Reindex to make aliases searchable
$ hypo reindex
```

### Resolve Aliases to IDs

```bash
# Exact alias match
$ hypo resolve "Quick Reference"
abc123

# Exact title match
$ hypo resolve "My Custom Title"
abc123

# Ambiguous or partial match shows candidates
$ hypo resolve "Quick"
No exact match for 'Quick'. Candidates:
  abc123	My Custom Title (alias: Quick Reference)
  def456	Quick Start Guide
```

### Search by Alias

```bash
# Include aliases in search results
$ hypo find "Reference" --aliases
abc123
def456
```

## Enhanced List and Search

### List with Titles

```bash
# Tab-separated ID and title
$ hypo ls --with-titles
abc123	My Custom Title
def456	Quick Start Guide
ghi789	Meeting Notes

# JSON format
$ hypo ls --format json
[
  {"id": "abc123", "title": "My Custom Title"},
  {"id": "def456", "title": "Quick Start Guide"},
  {"id": "ghi789", "title": "Meeting Notes"}
]
```

### Search with Custom Fields

```bash
# Display specific fields (tab-separated)
$ hypo find "research" --fields id,title
abc123	My Custom Title
def456	Research Methods

# Combine with snippets
$ hypo find "quantum" --snippets --fields id,title
abc123	My Custom Title	...discusses quantum computing...
def456	Quantum Physics	...introduction to quantum mechanics...
```

## Vault Diagnostics

Run health checks on your vault:

```bash
$ hypo doctor
✓ Vault exists: /home/user/vault
✓ Vault is writable
✓ Database exists: /home/user/vault/.hypo/index.sqlite
✓ Schema version: 2
✓ Sampled 10 notes, all parsed successfully

Counts:
  Notes: 42
  Links: 127
  Orphans: 3

✓ All checks passed
```

If issues are found, the command suggests fixes:
```bash
$ hypo doctor
✗ Database does not exist: /home/user/vault/.hypo/index.sqlite

Recommendations:
  Run: hypo reindex --full
```

## Enhanced Quartz Export

### Basic Export with Titles

```bash
$ hypo export quartz ./site
Exported to ./site

# Exported notes now include title as H1 if available
$ cat ./site/abc123/index.md
# My Custom Title

Content of the note...
```

### Export with Assets

```bash
# Copy images and assets to export
$ hypo export quartz ./site --assets-dir vault/assets

$ tree ./site
./site
├── abc123/
│   └── index.md
├── assets/
│   ├── image1.png
│   └── diagram.svg
└── graph.json
```

### KaTeX Math Support

If your notes contain math and config has `export.quartz.katex.auto = true`, a `.katex` flag file is created:

```bash
$ cat vault/math-note.md
# Math Note

Euler's identity: $e^{i\pi} + 1 = 0$

$ hypo export quartz ./site
# Creates ./site/.katex if math is detected
```

### Better Error Messages

Missing transclusions now have clearer error messages:

```markdown
<!-- Old -->
> MISSING: note123

<!-- New -->
> **Hypo:** missing note `note123`

<!-- Old -->
> MISSING ANCHOR: note123#^label

<!-- New -->
> **Hypo:** missing anchor `note123#^label`
```

## Tips

1. **Set default vault**: Use `--vault` or set up an alias:
   ```bash
   alias mynotes='hypo --vault ~/notes'
   mynotes ls
   ```

2. **Editor preference**: Set `EDITOR` environment variable:
   ```bash
   export EDITOR=nano
   hypo edit abc123
   ```

3. **JSON for scripting**: Use `--json` flag for machine-readable output:
   ```bash
   hypo --json lint | jq '.[] | select(.severity == "error")'
   ```

4. **Configuration**: Create `hypo.toml` to avoid repetitive flags:
   ```bash
   # Set up once
   cat > hypo.toml <<EOF
   [vault]
   root = "~/notes"
   EOF
   
   # Then just use
   hypo ls
   ```

5. **Aliases for quick access**: Use aliases to reference notes by name:
   ```bash
   # Set up aliases
   hypo meta set abc123 core/aliases='["Weekly Review","Review"]'
   hypo reindex
   
   # Resolve to ID
   NOTE=$(hypo resolve "Weekly Review")
   hypo edit "$NOTE"
   ```
