from pathlib import Path
import pytest
from fastapi.testclient import TestClient
from svo_api.main import create_app
from svo_api.settings import Settings

ROOT = Path(__file__).resolve().parents[3]
BUNDLE = ROOT / 'training/runs/v2/candidates/e5_tfidf/bundle'
# The v2 model routes ordinary text to low risk; cluster/review fixtures need a
# message it sends to review (v1 reviewed everything, including benign text).
REVIEW_TEXT = 'Your parcel is held. Pay the release fee at the link today to receive it.'


@pytest.fixture
def settings(tmp_path):
    return Settings(model_dir=BUNDLE, db_path=tmp_path / 'service.sqlite')


@pytest.fixture
def client(settings):
    with TestClient(create_app(settings)) as client:
        yield client
