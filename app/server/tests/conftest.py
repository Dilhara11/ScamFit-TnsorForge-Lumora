from pathlib import Path
import pytest
from fastapi.testclient import TestClient
from svo_api.main import create_app
from svo_api.settings import Settings

ROOT = Path(__file__).resolve().parents[3]


@pytest.fixture
def settings(tmp_path):
    return Settings(model_dir=ROOT / 'training/runs/final/bundle', db_path=tmp_path / 'service.sqlite')


@pytest.fixture
def client(settings):
    with TestClient(create_app(settings)) as client:
        yield client
