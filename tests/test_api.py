"""Tests for API functionality."""

import tempfile
from pathlib import Path

import pytest

try:
    from fastapi.testclient import TestClient

    from hypomnemata.api.app import create_app, generate_token
    FASTAPI_AVAILABLE = True
except ImportError:
    FASTAPI_AVAILABLE = False
    TestClient = None  # type: ignore

from hypomnemata.adapters.fs_storage import FsStorage
from hypomnemata.adapters.idgen import HexId
from hypomnemata.adapters.markdown_parser import MarkdownParser
from hypomnemata.adapters.resolver_index import DefaultResolver
from hypomnemata.adapters.sqlite_index import SQLiteIndex
from hypomnemata.adapters.yaml_codec import MarkdownNoteCodec, YamlFrontmatter
from hypomnemata.core.meta import MetaBag
from hypomnemata.core.model import Note
from hypomnemata.core.vault import Vault
from hypomnemata.runtime import Runtime


@pytest.fixture
def runtime():
    """Create a runtime with test vault."""
    with tempfile.TemporaryDirectory() as tmpdir:
        vault_path = Path(tmpdir) / "vault"
        vault_path.mkdir()
        
        storage = FsStorage(vault_path)
        codec = MarkdownNoteCodec(YamlFrontmatter())
        parser = MarkdownParser()
        vault = Vault(storage, parser, codec)
        
        db_path = Path(tmpdir) / "test.db"
        index = SQLiteIndex(db_path=db_path, vault_path=vault_path, vault=vault)
        resolver = DefaultResolver(vault)
        idgen = HexId(nbytes=4)
        
        # Mock config
        class MockConfig:
            pass
        
        rt = Runtime(
            vault=vault,
            index=index,
            resolver=resolver,
            idgen=idgen,
            config=MockConfig(),  # type: ignore
        )
        
        yield rt


@pytest.mark.skipif(not FASTAPI_AVAILABLE, reason="fastapi not installed")
def test_health_endpoint(runtime):
    """Test /health endpoint."""
    app = create_app(runtime, token=None)
    client = TestClient(app)
    
    response = client.get("/health")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "ok"
    assert data["schema_version"] == "2"


@pytest.mark.skipif(not FASTAPI_AVAILABLE, reason="fastapi not installed")
def test_auth_required(runtime):
    """Test that endpoints require authentication when token is set."""
    token = generate_token()
    app = create_app(runtime, token=token)
    client = TestClient(app)
    
    # Without token should get 401
    response = client.get("/health")
    assert response.status_code == 401
    
    # With token should work
    response = client.get("/health", headers={"Authorization": f"Bearer {token}"})
    assert response.status_code == 200


@pytest.mark.skipif(not FASTAPI_AVAILABLE, reason="fastapi not installed")
def test_get_note(runtime):
    """Test /notes/{id} endpoint."""
    # Create a test note
    note = Note(
        id="test123",
        meta=MetaBag({"title": "Test Note"}),
        body=runtime.vault.parser.parse("# Test\n\nContent here.", "test123")
    )
    runtime.vault.put(note)
    
    app = create_app(runtime, token=None)
    client = TestClient(app)
    
    response = client.get("/notes/test123")
    assert response.status_code == 200
    data = response.json()
    assert data["id"] == "test123"
    assert "meta" in data
    assert "body" in data
    assert "Test" in data["body"]


@pytest.mark.skipif(not FASTAPI_AVAILABLE, reason="fastapi not installed")
def test_get_note_not_found(runtime):
    """Test /notes/{id} with nonexistent note."""
    app = create_app(runtime, token=None)
    client = TestClient(app)
    
    response = client.get("/notes/nonexistent")
    assert response.status_code == 404


@pytest.mark.skipif(not FASTAPI_AVAILABLE, reason="fastapi not installed")
def test_yank_endpoint(runtime):
    """Test /yank endpoint."""
    note = Note(
        id="test123",
        meta=MetaBag({"title": "Test"}),
        body=runtime.vault.parser.parse("# Test\n\n## Section\n\nContent.", "test123")
    )
    runtime.vault.put(note)
    
    app = create_app(runtime, token=None)
    client = TestClient(app)
    
    # Yank whole note
    response = client.get("/yank?id=test123")
    assert response.status_code == 200
    data = response.json()
    assert "text" in data
    assert "Test" in data["text"]
    
    # Yank with anchor
    response = client.get("/yank?id=test123&anchor=section")
    assert response.status_code == 200
    data = response.json()
    assert "Section" in data["text"]


@pytest.mark.skipif(not FASTAPI_AVAILABLE, reason="fastapi not installed")
def test_locate_endpoint(runtime):
    """Test /locate endpoint."""
    note = Note(
        id="test123",
        meta=MetaBag({"title": "Test"}),
        body=runtime.vault.parser.parse("# Test\n\nContent.", "test123")
    )
    runtime.vault.put(note)
    
    app = create_app(runtime, token=None)
    client = TestClient(app)
    
    response = client.get("/locate?id=test123")
    assert response.status_code == 200
    data = response.json()
    assert data["id"] == "test123"
    assert "range" in data
    assert "lines" in data
    assert "path" in data


@pytest.mark.skipif(not FASTAPI_AVAILABLE, reason="fastapi not installed")
def test_search_endpoint(runtime):
    """Test /search endpoint."""
    # Create test notes
    note1 = Note(
        id="note1",
        meta=MetaBag({"title": "First"}),
        body=runtime.vault.parser.parse("# First\n\nPython code here.", "note1")
    )
    note2 = Note(
        id="note2",
        meta=MetaBag({"title": "Second"}),
        body=runtime.vault.parser.parse("# Second\n\nJavaScript code.", "note2")
    )
    runtime.vault.put(note1)
    runtime.vault.put(note2)
    
    # Build index
    runtime.index.rebuild(full=True)
    
    app = create_app(runtime, token=None)
    client = TestClient(app)
    
    response = client.get("/search?q=python")
    assert response.status_code == 200
    data = response.json()
    assert len(data) >= 1
    assert any(item["id"] == "note1" for item in data)


@pytest.mark.skipif(not FASTAPI_AVAILABLE, reason="fastapi not installed")
def test_backrefs_endpoint(runtime):
    """Test /backrefs endpoint."""
    # Create notes with links
    note1 = Note(
        id="note1",
        meta=MetaBag({"title": "First"}),
        body=runtime.vault.parser.parse("# First\n\nSee [[note2]].", "note1")
    )
    note2 = Note(
        id="note2",
        meta=MetaBag({"title": "Second"}),
        body=runtime.vault.parser.parse("# Second\n\nContent.", "note2")
    )
    runtime.vault.put(note1)
    runtime.vault.put(note2)
    
    # Build index
    runtime.index.rebuild(full=True)
    
    app = create_app(runtime, token=None)
    client = TestClient(app)
    
    response = client.get("/backrefs?id=note2")
    assert response.status_code == 200
    data = response.json()
    assert len(data) >= 1
    assert any(item["source"] == "note1" for item in data)


@pytest.mark.skipif(not FASTAPI_AVAILABLE, reason="fastapi not installed")
def test_graph_endpoint(runtime):
    """Test /graph endpoint."""
    # Create notes with links
    note1 = Note(
        id="note1",
        meta=MetaBag({"title": "First"}),
        body=runtime.vault.parser.parse("# First\n\n[[note2]]", "note1")
    )
    note2 = Note(
        id="note2",
        meta=MetaBag({"title": "Second"}),
        body=runtime.vault.parser.parse("# Second", "note2")
    )
    runtime.vault.put(note1)
    runtime.vault.put(note2)
    
    # Build index
    runtime.index.rebuild(full=True)
    
    app = create_app(runtime, token=None)
    client = TestClient(app)
    
    response = client.get("/graph")
    assert response.status_code == 200
    data = response.json()
    assert "nodes" in data
    assert "edges" in data
    assert len(data["nodes"]) >= 2
    assert len(data["edges"]) >= 1
