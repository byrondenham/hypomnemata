"""SQLite-based durable index with FTS5 search and incremental updates."""

import hashlib
import re
import sqlite3
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from ..core.model import Block, Link, NoteId
from ..core.ports import Index
from ..core.vault import Vault


@dataclass
class SQLiteIndex(Index):
    """
    SQLite-backed index with incremental updates and FTS5 search.
    
    The DB is a cache that can be rebuilt; flat files remain source of truth.
    """
    
    db_path: Path
    vault_path: Path
    vault: Vault
    
    def _conn(self) -> sqlite3.Connection:
        """Get a connection to the SQLite database."""
        conn = sqlite3.connect(str(self.db_path), check_same_thread=False)
        conn.execute("PRAGMA journal_mode=WAL")
        conn.execute("PRAGMA synchronous=NORMAL")
        conn.execute("PRAGMA temp_store=MEMORY")
        return conn
    
    def _init_schema(self) -> None:
        """Create tables if they don't exist."""
        conn = self._conn()
        try:
            # Meta table
            conn.execute("""
                CREATE TABLE IF NOT EXISTS meta (
                    key TEXT PRIMARY KEY,
                    value TEXT NOT NULL
                )
            """)
            
            # Notes table
            conn.execute("""
                CREATE TABLE IF NOT EXISTS notes (
                    id TEXT PRIMARY KEY,
                    mtime_ns INTEGER NOT NULL,
                    size_bytes INTEGER NOT NULL,
                    hash TEXT,
                    title TEXT,
                    has_math INTEGER NOT NULL DEFAULT 0
                )
            """)
            
            # Blocks table
            conn.execute("""
                CREATE TABLE IF NOT EXISTS blocks (
                    note_id TEXT NOT NULL,
                    kind TEXT NOT NULL,
                    start INTEGER NOT NULL,
                    end INTEGER NOT NULL,
                    level INTEGER,
                    slug TEXT,
                    label TEXT,
                    PRIMARY KEY (note_id, start),
                    FOREIGN KEY (note_id) REFERENCES notes(id) ON DELETE CASCADE
                )
            """)
            
            # Links table
            conn.execute("""
                CREATE TABLE IF NOT EXISTS links (
                    src TEXT NOT NULL,
                    dst TEXT NOT NULL,
                    start INTEGER NOT NULL,
                    end INTEGER NOT NULL,
                    rel TEXT,
                    anchor_kind TEXT,
                    anchor_value TEXT,
                    PRIMARY KEY (src, start),
                    FOREIGN KEY (src) REFERENCES notes(id) ON DELETE CASCADE
                )
            """)
            
            # KV table for metadata
            conn.execute("""
                CREATE TABLE IF NOT EXISTS kv (
                    note_id TEXT NOT NULL,
                    key TEXT NOT NULL,
                    value TEXT,
                    FOREIGN KEY (note_id) REFERENCES notes(id) ON DELETE CASCADE
                )
            """)
            
            # Create index for kv lookups
            conn.execute("""
                CREATE INDEX IF NOT EXISTS kv_note_key_idx ON kv(note_id, key)
            """)
            conn.execute("""
                CREATE INDEX IF NOT EXISTS kv_key_value_idx ON kv(key, value)
            """)
            
            # FTS5 virtual table
            conn.execute("""
                CREATE VIRTUAL TABLE IF NOT EXISTS fts USING fts5(
                    id UNINDEXED,
                    body,
                    title,
                    tokenize = "unicode61 remove_diacritics 2"
                )
            """)
            
            # Create indexes
            conn.execute("CREATE INDEX IF NOT EXISTS links_dst_idx ON links(dst)")
            conn.execute("CREATE INDEX IF NOT EXISTS links_src_idx ON links(src)")
            conn.execute("CREATE INDEX IF NOT EXISTS blocks_label_idx ON blocks(note_id, label)")
            conn.execute("CREATE INDEX IF NOT EXISTS blocks_slug_idx ON blocks(note_id, slug)")
            
            # Set schema version
            conn.execute("""
                INSERT INTO meta(key, value) VALUES('schema_version', '2')
                ON CONFLICT(key) DO UPDATE SET value=excluded.value
            """)
            
            conn.commit()
        finally:
            conn.close()
    
    def _migrate_schema(self, conn: sqlite3.Connection) -> None:
        """Migrate schema from older versions."""
        # Get current schema version
        try:
            row = conn.execute(
                "SELECT value FROM meta WHERE key = 'schema_version'"
            ).fetchone()
            current_version = int(row[0]) if row else 0
        except Exception:
            current_version = 0
        
        # Migrate from v1 to v2: update kv table to allow multiple values per key
        if current_version < 2:
            try:
                # Drop old kv table if it exists with the old schema
                conn.execute("DROP TABLE IF EXISTS kv")
                
                # Recreate with new schema
                conn.execute("""
                    CREATE TABLE IF NOT EXISTS kv (
                        note_id TEXT NOT NULL,
                        key TEXT NOT NULL,
                        value TEXT,
                        FOREIGN KEY (note_id) REFERENCES notes(id) ON DELETE CASCADE
                    )
                """)
                
                # Create indexes
                conn.execute("""
                    CREATE INDEX IF NOT EXISTS kv_note_key_idx ON kv(note_id, key)
                """)
                conn.execute("""
                    CREATE INDEX IF NOT EXISTS kv_key_value_idx ON kv(key, value)
                """)
                
                # Update version
                conn.execute("""
                    INSERT INTO meta(key, value) VALUES('schema_version', '2')
                    ON CONFLICT(key) DO UPDATE SET value=excluded.value
                """)
                
                conn.commit()
            except Exception as e:
                print(f"Warning: Schema migration failed: {e}")
    
    def _ensure_schema(self) -> None:
        """Ensure DB exists and schema is initialized."""
        # Create parent directory if needed
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        
        # Check if DB exists and is valid
        if self.db_path.exists():
            try:
                conn = self._conn()
                # Try a simple query to check if DB is valid
                conn.execute("SELECT 1").fetchone()
                
                # Run migrations if needed
                self._migrate_schema(conn)
                conn.close()
            except sqlite3.DatabaseError:
                # DB is corrupt, backup and recreate
                timestamp = int(time.time())
                backup_path = self.db_path.with_suffix(f".bad-{timestamp}.sqlite")
                self.db_path.rename(backup_path)
                print(f"Warning: Corrupt DB backed up to {backup_path}")
        
        self._init_schema()
    
    def _get_file_stats(self, note_id: str) -> tuple[int, int] | None:
        """Get mtime_ns and size_bytes for a note file, or None if not found."""
        file_path = self.vault_path / f"{note_id}.md"
        if not file_path.exists():
            return None
        stat = file_path.stat()
        return (stat.st_mtime_ns, stat.st_size)
    
    def _compute_hash(self, note_id: str) -> str | None:
        """Compute SHA256 hash of a note file."""
        file_path = self.vault_path / f"{note_id}.md"
        if not file_path.exists():
            return None
        return hashlib.sha256(file_path.read_bytes()).hexdigest()
    
    def _is_dirty(self, note_id: str, use_hash: bool, conn: sqlite3.Connection) -> bool:
        """Check if a note needs reindexing."""
        stats = self._get_file_stats(note_id)
        if stats is None:
            # File doesn't exist, not dirty (will be handled as removed)
            return False
        
        mtime_ns, size_bytes = stats
        
        # Check DB for existing record
        row = conn.execute(
            "SELECT mtime_ns, size_bytes, hash FROM notes WHERE id = ?",
            (note_id,)
        ).fetchone()
        
        if row is None:
            # Not in DB, definitely dirty
            return True
        
        db_mtime, db_size, db_hash = row
        
        # Quick check: mtime or size changed
        if db_mtime != mtime_ns or db_size != size_bytes:
            return True
        
        # Optional hash check for certainty
        if use_hash:
            current_hash = self._compute_hash(note_id)
            if current_hash != db_hash:
                return True
        
        return False
    
    def _extract_title(self, note: Any) -> str:
        """Extract title from note using the stable heuristic."""
        # Try core/title meta first
        if "core/title" in note.meta:
            return str(note.meta["core/title"])
        
        # Try legacy title meta
        if "title" in note.meta:
            return str(note.meta["title"])
        
        # Try first heading
        for block in note.body.blocks:
            if block.kind == "heading" and block.heading_text:
                return str(block.heading_text)
        
        # Try first non-empty line
        for line in note.body.raw.splitlines():
            stripped = line.strip()
            if stripped and not stripped.startswith("---"):
                return str(stripped)
        
        return ""
    
    def _detect_math(self, body_raw: str) -> bool:
        """Detect if note contains math expressions."""
        if "$" not in body_raw:
            return False
        # Simple check for unescaped $ signs
        return bool(re.search(r'(?<!\\)\$', body_raw))
    
    def _index_note(self, note_id: str, use_hash: bool, conn: sqlite3.Connection) -> bool:
        """Index a single note. Returns True on success, False on error."""
        try:
            # Load note
            note = self.vault.get(note_id)
            if note is None:
                return False
            
            # Get file stats
            stats = self._get_file_stats(note_id)
            if stats is None:
                return False
            mtime_ns, size_bytes = stats
            
            # Compute hash if requested
            file_hash = self._compute_hash(note_id) if use_hash else None
            
            # Extract title and detect math
            title = self._extract_title(note)
            has_math = 1 if self._detect_math(note.body.raw) else 0
            
            # Begin transaction
            conn.execute("BEGIN IMMEDIATE")
            
            try:
                # Upsert into notes table
                conn.execute("""
                    INSERT INTO notes (id, mtime_ns, size_bytes, hash, title, has_math)
                    VALUES (?, ?, ?, ?, ?, ?)
                    ON CONFLICT(id) DO UPDATE SET
                        mtime_ns = excluded.mtime_ns,
                        size_bytes = excluded.size_bytes,
                        hash = excluded.hash,
                        title = excluded.title,
                        has_math = excluded.has_math
                """, (note_id, mtime_ns, size_bytes, file_hash, title, has_math))
                
                # Delete existing blocks and links
                conn.execute("DELETE FROM blocks WHERE note_id = ?", (note_id,))
                conn.execute("DELETE FROM links WHERE src = ?", (note_id,))
                conn.execute("DELETE FROM kv WHERE note_id = ?", (note_id,))
                
                # Insert blocks
                for block in note.body.blocks:
                    label_name = block.label.name if block.label else None
                    conn.execute("""
                        INSERT INTO blocks (note_id, kind, start, end, level, slug, label)
                        VALUES (?, ?, ?, ?, ?, ?, ?)
                    """, (
                        note_id,
                        block.kind,
                        block.range.start,
                        block.range.end,
                        block.heading_level,
                        block.heading_slug,
                        label_name
                    ))
                
                # Insert links
                for link in note.body.links:
                    anchor_kind = link.target.anchor.kind if link.target.anchor else None
                    anchor_value = link.target.anchor.value if link.target.anchor else None
                    link_start = link.range.start if link.range else 0
                    link_end = link.range.end if link.range else 0
                    
                    conn.execute("""
                        INSERT INTO links (src, dst, start, end, rel, anchor_kind, anchor_value)
                        VALUES (?, ?, ?, ?, ?, ?, ?)
                    """, (
                        note_id,
                        link.target.id,
                        link_start,
                        link_end,
                        link.target.rel,
                        anchor_kind,
                        anchor_value
                    ))
                
                # Extract and insert aliases from core/aliases metadata
                if "core/aliases" in note.meta:
                    aliases = note.meta["core/aliases"]
                    if isinstance(aliases, list):
                        for alias in aliases:
                            if isinstance(alias, str):
                                conn.execute("""
                                    INSERT INTO kv (note_id, key, value)
                                    VALUES (?, ?, ?)
                                """, (note_id, "core/alias", alias))
                
                # Update FTS
                # Delete old entry
                conn.execute("DELETE FROM fts WHERE id = ?", (note_id,))
                # Insert new entry
                conn.execute(
                    "INSERT INTO fts (id, body, title) VALUES (?, ?, ?)",
                    (note_id, note.body.raw, title)
                )
                
                # Commit transaction
                conn.commit()
                return True
                
            except Exception as e:
                conn.rollback()
                print(f"Warning: Failed to index {note_id}: {e}")
                return False
                
        except Exception as e:
            print(f"Warning: Failed to load {note_id}: {e}")
            return False
    
    def rebuild(self, full: bool = False, use_hash: bool = False) -> dict[str, int]:
        """
        Rebuild or update the index.
        
        Args:
            full: If True, force full rebuild. Otherwise incremental.
            use_hash: If True, use SHA256 hash for change detection.
        
        Returns:
            Dictionary with counts: scanned, dirty, inserted, updated, removed, failed
        """
        self._ensure_schema()
        
        conn = self._conn()
        
        try:
            counts = {
                "scanned": 0,
                "dirty": 0,
                "inserted": 0,
                "updated": 0,
                "removed": 0,
                "failed": 0,
            }
            
            # Get all note IDs from filesystem
            file_ids = set(self.vault.list_ids())
            counts["scanned"] = len(file_ids)
            
            # Get all note IDs from DB
            db_ids = set(
                row[0] for row in conn.execute("SELECT id FROM notes").fetchall()
            )
            
            # Find notes to remove (in DB but not on filesystem)
            removed_ids = db_ids - file_ids
            for note_id in removed_ids:
                conn.execute("DELETE FROM notes WHERE id = ?", (note_id,))
                conn.execute("DELETE FROM fts WHERE id = ?", (note_id,))
                counts["removed"] += 1
            conn.commit()
            
            # Process each file
            for note_id in file_ids:
                is_new = note_id not in db_ids
                
                # Check if dirty (or full rebuild)
                if full or self._is_dirty(note_id, use_hash, conn):
                    counts["dirty"] += 1
                    
                    # Index the note
                    success = self._index_note(note_id, use_hash, conn)
                    if success:
                        if is_new:
                            counts["inserted"] += 1
                        else:
                            counts["updated"] += 1
                    else:
                        counts["failed"] += 1
            
            # Vacuum and analyze after full rebuild
            if full:
                conn.execute("VACUUM")
                conn.execute("ANALYZE")
            
            return counts
            
        finally:
            conn.close()
    
    def update_notes(self, changed: set[str], deleted: set[str]) -> dict[str, int]:
        """
        Incrementally update specific notes in the index.
        
        Args:
            changed: Set of note IDs that were created or modified
            deleted: Set of note IDs that were deleted
        
        Returns:
            Dictionary with counts: updated, inserted, removed
        """
        self._ensure_schema()
        
        conn = self._conn()
        conn.execute("PRAGMA busy_timeout=3000")
        
        try:
            counts = {
                "updated": 0,
                "inserted": 0,
                "removed": 0,
            }
            
            # Handle deletions
            for note_id in deleted:
                # Delete note and cascading data
                conn.execute("DELETE FROM notes WHERE id = ?", (note_id,))
                conn.execute("DELETE FROM fts WHERE id = ?", (note_id,))
                counts["removed"] += 1
            conn.commit()
            
            # Get existing note IDs
            db_ids = set(
                row[0] for row in conn.execute(
                    "SELECT id FROM notes WHERE id IN ({})".format(
                        ",".join("?" * len(changed))
                    ),
                    tuple(changed)
                ).fetchall()
            ) if changed else set()
            
            # Handle changed notes
            for note_id in changed:
                is_new = note_id not in db_ids
                
                # Index the note (use_hash=False for speed)
                success = self._index_note(note_id, False, conn)
                if success:
                    if is_new:
                        counts["inserted"] += 1
                    else:
                        counts["updated"] += 1
            
            return counts
            
        finally:
            conn.close()
    
    def links_out(self, id: NoteId) -> list[Link]:
        """Get all outgoing links from a note."""
        conn = self._conn()
        try:
            rows = conn.execute("""
                SELECT dst, start, end, rel, anchor_kind, anchor_value
                FROM links
                WHERE src = ?
                ORDER BY start
            """, (id,)).fetchall()
            
            from ..core.model import Anchor, LinkTarget, Range
            
            links = []
            for row in rows:
                dst, start, end, rel, anchor_kind, anchor_value = row
                
                anchor = None
                if anchor_kind and anchor_value:
                    anchor = Anchor(kind=anchor_kind, value=anchor_value)
                
                target = LinkTarget(id=dst, anchor=anchor, rel=rel)
                links.append(Link(source=id, target=target, range=Range(start, end)))
            
            return links
        finally:
            conn.close()
    
    def links_in(self, id: NoteId) -> list[Link]:
        """Get all incoming links to a note."""
        conn = self._conn()
        try:
            rows = conn.execute("""
                SELECT src, start, end, rel, anchor_kind, anchor_value
                FROM links
                WHERE dst = ?
                ORDER BY src, start
            """, (id,)).fetchall()
            
            from ..core.model import Anchor, LinkTarget, Range
            
            links = []
            for row in rows:
                src, start, end, rel, anchor_kind, anchor_value = row
                
                anchor = None
                if anchor_kind and anchor_value:
                    anchor = Anchor(kind=anchor_kind, value=anchor_value)
                
                target = LinkTarget(id=id, anchor=anchor, rel=rel)
                links.append(Link(source=src, target=target, range=Range(start, end)))
            
            return links
        finally:
            conn.close()
    
    def blocks(self, id: NoteId) -> list[Block]:
        """Get all blocks for a note."""
        conn = self._conn()
        try:
            rows = conn.execute("""
                SELECT kind, start, end, level, slug, label
                FROM blocks
                WHERE note_id = ?
                ORDER BY start
            """, (id,)).fetchall()
            
            from ..core.model import BlockLabel, Range
            
            blocks = []
            for row in rows:
                kind, start, end, level, slug, label_name = row
                
                label = BlockLabel(name=label_name) if label_name else None
                
                block = Block(
                    kind=kind,
                    range=Range(start, end),
                    label=label,
                    heading_level=level,
                    heading_slug=slug,
                )
                blocks.append(block)
            
            return blocks
        finally:
            conn.close()
    
    def search(self, query: str, limit: int = 50) -> list[NoteId]:
        """Search using FTS5."""
        conn = self._conn()
        try:
            # Check if FTS has any data
            count = conn.execute("SELECT COUNT(*) FROM fts").fetchone()[0]
            if count == 0:
                print("Index is empty or stale. Run: hypo reindex")
                return []
            
            rows = conn.execute("""
                SELECT id FROM fts
                WHERE fts MATCH ?
                ORDER BY rank
                LIMIT ?
            """, (query, limit)).fetchall()
            
            return [row[0] for row in rows]
        finally:
            conn.close()
    
    def snippet(self, id: NoteId, query: str) -> str | None:
        """Get a snippet with highlighted matches."""
        conn = self._conn()
        try:
            row = conn.execute("""
                SELECT snippet(fts, 1, '<b>', '</b>', ' … ', 64)
                FROM fts
                WHERE id = ? AND fts MATCH ?
            """, (id, query)).fetchone()
            
            return row[0] if row else None
        finally:
            conn.close()
    
    def orphans(self) -> list[NoteId]:
        """Find notes with no incoming or outgoing links."""
        conn = self._conn()
        try:
            rows = conn.execute("""
                SELECT id FROM notes
                WHERE id NOT IN (SELECT src FROM links)
                  AND id NOT IN (SELECT dst FROM links)
                ORDER BY id
            """).fetchall()
            
            return [row[0] for row in rows]
        finally:
            conn.close()
    
    def graph_data(self) -> dict[str, Any]:
        """Export graph data for visualization."""
        conn = self._conn()
        try:
            # Get all notes
            note_rows = conn.execute("SELECT id, title FROM notes ORDER BY id").fetchall()
            nodes = [{"id": row[0], "title": row[1] or ""} for row in note_rows]
            
            # Get all links (deduplicated)
            link_rows = conn.execute("""
                SELECT DISTINCT src, dst FROM links ORDER BY src, dst
            """).fetchall()
            edges = [{"source": row[0], "target": row[1]} for row in link_rows]
            
            return {"nodes": nodes, "edges": edges}
        finally:
            conn.close()
