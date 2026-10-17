"""Verify trusted artifact + source identity before any joblib load."""
import json
from svo_api.settings import Settings
from svo_api.services.engine import load_runtime

settings = Settings.from_env()
runtime, manifest = load_runtime(settings)
runtime.predict('Service startup check.')
print(json.dumps({'model_version': manifest['version'], 'candidate': manifest['candidate'], 'verified': True}))
