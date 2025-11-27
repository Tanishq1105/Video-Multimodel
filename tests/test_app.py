import sys
from unittest.mock import MagicMock

# Mock chromadb before importing backend modules
mock_chroma = MagicMock()
sys.modules["chromadb"] = mock_chroma
sys.modules["chromadb.utils"] = MagicMock()
sys.modules["chromadb.utils.embedding_functions"] = MagicMock()

import pytest
import os
from backend.app import app, get_session
from backend.models import Video
from sqlmodel import Session, SQLModel, create_engine
from sqlmodel.pool import StaticPool

@pytest.fixture(name="session")
def session_fixture():
    engine = create_engine(
        "sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool
    )
    SQLModel.metadata.create_all(engine)
    with Session(engine) as session:
        yield session

@pytest.fixture(name="client")
def client_fixture(session: Session):
    def get_session_override():
        return session

    app.dependency_overrides = {} # Flask doesn't have dependency overrides like FastAPI, but we can mock
    # For Flask, we usually just use the test client and mock the DB session if needed.
    # But since we are using a global engine in app.py, it's harder to override.
    # For simplicity in this quick test, we'll just test the routes without DB mocking 
    # or we'd need to refactor app.py to be more testable (factory pattern).
    
    # Let's just use the app's test client and rely on the fact that it uses a local DB file (or we can set env var)
    app.config['TESTING'] = True
    with app.test_client() as client:
        yield client

def test_read_main(client):
    response = client.get("/")
    assert response.status_code == 200
    assert b"Video Tutor AI" in response.data

def test_upload_no_file(client):
    response = client.post("/upload", data={})
    assert response.status_code == 302 # Redirects

def test_video_page_404(client):
    response = client.get("/video/999")
    assert response.status_code == 404
