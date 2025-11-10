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

4. **Piping content**: Create notes from stdin:
   ```bash
   echo "# Quick Note\n\nContent here" | hypo new --title "Quick"
   ```
