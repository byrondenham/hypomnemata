"""FastAPI application for hypomnemata local JSON API."""

import secrets
from typing import Any

try:
    from fastapi import Depends, FastAPI, HTTPException, Query, Security
    from fastapi.middleware.cors import CORSMiddleware
    from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

    FASTAPI_AVAILABLE = True
except ImportError:
    FASTAPI_AVAILABLE = False

    # Stub definitions for when FastAPI is not available
    def _stub_depends(x: Any) -> Any:
        return x

    def _stub_query(*args: Any, **kwargs: Any) -> None:
        return None

    def _stub_security(x: Any) -> Any:
        return x

    FastAPI = object
    Depends = _stub_depends
    HTTPException = Exception
    Query = _stub_query
    Security = _stub_security
    HTTPAuthorizationCredentials = object
    HTTPBearer = object
    CORSMiddleware = object

from ..core.model import Anchor
from ..core.slicer import slice_by_anchor
from ..locate import locate_note


def create_app(runtime: Any, token: str | None = None, enable_cors: bool = False) -> Any:
    """
    Create FastAPI application with runtime injected.

    Args:
        runtime: Runtime instance with vault and index
        token: Bearer token for authentication (None to disable auth)
        enable_cors: Enable CORS middleware

    Returns:
        FastAPI application instance
    """
    if not FASTAPI_AVAILABLE:
        raise ImportError("FastAPI not available. Install with: pip install hypomnemata[api]")

    app = FastAPI(
        title="Hypomnemata API",
        description="Local JSON API for hypomnemata vault",
        version="0.1.0",
        docs_url="/docs" if token is None else None,
        redoc_url="/redoc" if token is None else None,
    )

    # Add CORS middleware if enabled
    if enable_cors:
        app.add_middleware(
            CORSMiddleware,
            allow_origins=["*"],
            allow_credentials=True,
            allow_methods=["*"],
            allow_headers=["*"],
        )

    # Security setup
    if token:
        security_scheme = HTTPBearer(auto_error=False)

        async def verify_token(
            credentials: HTTPAuthorizationCredentials | None = Security(security_scheme),  # noqa: B008
        ) -> None:
            """Verify bearer token."""
            if credentials is None or credentials.credentials != token:
                raise HTTPException(status_code=401, detail="Invalid or missing token")
    else:

        async def verify_token(credentials: HTTPAuthorizationCredentials | None = None) -> None:
            """No-op when auth is disabled."""
            return None

    @app.get("/health")  # type: ignore[misc]
    async def health(auth: None = Depends(verify_token)) -> dict[str, Any]:
        """Health check endpoint."""
        return {"status": "ok", "schema_version": "2"}

    @app.get("/notes/{note_id}")  # type: ignore[misc]
    async def get_note(note_id: str, auth: None = Depends(verify_token)) -> dict[str, Any]:
        """Get note metadata and body."""
        note = runtime.vault.get(note_id)
        if note is None:
            raise HTTPException(status_code=404, detail=f"Note {note_id} not found")

        return {
            "id": note.id,
            "meta": dict(note.meta),
            "body": note.body.raw,
        }

    @app.get("/yank")  # type: ignore[misc]
    async def yank(
        id: str = Query(..., description="Note ID"),
        anchor: str | None = Query(None, description="Anchor (slug or ^label)"),
        plain: bool = Query(False, description="Strip fence markers from code blocks"),
        auth: None = Depends(verify_token),
    ) -> dict[str, Any]:
        """Get a slice of a note."""
        # Get note
        note = runtime.vault.get(id)
        if note is None:
            raise HTTPException(status_code=404, detail=f"Note {id} not found")

        # Parse anchor
        anchor_obj = None
        if anchor:
            if anchor.startswith("^"):
                anchor_obj = Anchor(kind="block", value=anchor[1:])
            else:
                anchor_obj = Anchor(kind="heading", value=anchor)

        # Get slice
        start, end = slice_by_anchor(note, anchor_obj)

        if start == end and anchor_obj is not None:
            raise HTTPException(status_code=404, detail=f"Anchor {anchor} not found")

        slice_text = note.body.raw[start:end]

        # Handle plain flag
        if plain and slice_text.strip().startswith("```"):
            lines = slice_text.splitlines(keepends=True)
            if (
                len(lines) >= 2
                and lines[0].strip().startswith("```")
                and lines[-1].strip() == "```"
            ):
                slice_text = "".join(lines[1:-1])
            elif len(lines) >= 2 and lines[0].strip().startswith("```"):
                for i in range(len(lines) - 1, 0, -1):
                    if lines[i].strip() == "```":
                        slice_text = "".join(lines[1:i])
                        break

        return {"text": slice_text}

    @app.get("/locate")  # type: ignore[misc]
    async def locate(
        id: str = Query(..., description="Note ID"),
        anchor: str | None = Query(None, description="Anchor (slug or ^label)"),
        auth: None = Depends(verify_token),
    ) -> dict[str, Any]:
        """Get precise location information for a note or anchor."""
        # Get note
        note = runtime.vault.get(id)
        if note is None:
            raise HTTPException(status_code=404, detail=f"Note {id} not found")

        # Parse anchor
        anchor_obj = None
        if anchor:
            if anchor.startswith("^"):
                anchor_obj = Anchor(kind="block", value=anchor[1:])
            else:
                anchor_obj = Anchor(kind="heading", value=anchor)

        # Get location
        location = locate_note(note, anchor_obj, format_type="json")

        if not location or "id" not in location:
            raise HTTPException(status_code=404, detail=f"Anchor {anchor} not found")

        # Add path
        note_path = runtime.vault.storage._path(id)
        if "path" not in location:
            location["path"] = str(note_path.absolute())

        return location

    @app.get("/search")  # type: ignore[misc]
    async def search(
        q: str = Query(..., description="Search query"),
        limit: int = Query(50, description="Maximum results", le=100),
        snippets: bool = Query(False, description="Include snippets"),
        auth: None = Depends(verify_token),
    ) -> list[dict[str, Any]]:
        """Full-text search."""
        from ..adapters.sqlite_index import SQLiteIndex

        if not isinstance(runtime.index, SQLiteIndex):
            raise HTTPException(status_code=500, detail="Search requires SQLiteIndex")

        results = list(runtime.index.search(q, limit=limit))

        output = []
        for note_id in results:
            # Get title from DB
            conn = runtime.index._conn()
            try:
                row = conn.execute("SELECT title FROM notes WHERE id = ?", (note_id,)).fetchone()
                title = row[0] if row else ""
            finally:
                conn.close()

            item: dict[str, Any] = {"id": note_id, "title": title}

            if snippets:
                snippet = runtime.index.snippet(note_id, q)
                if snippet:
                    item["snippet"] = snippet

            output.append(item)

        return output

    @app.get("/backrefs")  # type: ignore[misc]
    async def backrefs(
        id: str = Query(..., description="Note ID"),
        context: int = Query(2, description="Context lines", ge=0),
        auth: None = Depends(verify_token),
    ) -> list[dict[str, Any]]:
        """Get incoming links with context."""
        incoming = runtime.index.links_in(id)

        output = []
        for link in incoming:
            note = runtime.vault.get(link.source)
            if note and link.range:
                # Extract context lines around the link
                lines = note.body.raw[: link.range.start].splitlines()
                start_line = max(0, len(lines) - context)
                end_line = len(lines) + context
                context_lines = note.body.raw.splitlines()[start_line:end_line]

                output.append(
                    {
                        "source": link.source,
                        "start": link.range.start,
                        "end": link.range.end,
                        "context": "\n".join(context_lines),
                    }
                )

        return output

    @app.get("/graph")  # type: ignore[misc]
    async def graph(auth: None = Depends(verify_token)) -> dict[str, Any]:
        """Get graph data."""
        from ..adapters.sqlite_index import SQLiteIndex

        if not isinstance(runtime.index, SQLiteIndex):
            raise HTTPException(status_code=500, detail="Graph requires SQLiteIndex")

        return runtime.index.graph_data()

    return app


def generate_token() -> str:
    """Generate a random bearer token."""
    return secrets.token_urlsafe(32)
