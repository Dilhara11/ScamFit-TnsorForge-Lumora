"""Verify trusted artifact + source identity before any joblib load."""
import json
from svo_api.settings import Settings
from svo_api.services.engine import verify_runtime
from svo.model import Runtime

settings = Settings.from_env()
manifest = verify_runtime(settings)
runtime = Runtime(settings.model_dir)
runtime.predict('Service startup check.')
print(json.dumps({'model_version': manifest['version'], 'candidate': manifest['candidate'], 'verified': True}))
