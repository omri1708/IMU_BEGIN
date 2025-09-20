from fastapi.testclient import TestClient
import pytest
from services.backend.app import app

@pytest.fixture
def client():
    return TestClient(app)
