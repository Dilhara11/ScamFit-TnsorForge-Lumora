"""Opt in with SVO_TEST_URL; does not start or modify Docker itself."""
import importlib.util
import os
from pathlib import Path
import pytest


@pytest.mark.skipif(not os.getenv('SVO_TEST_URL'), reason='Set SVO_TEST_URL for real HTTP/container checks')
def test_running_container():
    path = Path(__file__).resolve().parents[1]/'scripts/smoke.py'
    spec = importlib.util.spec_from_file_location('svo_smoke', path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    result = module.run(os.environ['SVO_TEST_URL'], os.getenv('SVO_API_KEY'))
    assert result['passed']
