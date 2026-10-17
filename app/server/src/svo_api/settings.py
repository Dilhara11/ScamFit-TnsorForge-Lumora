import json
import os
from dataclasses import dataclass, field
from pathlib import Path


@dataclass(frozen=True)
class Settings:
    model_dir: Path = Path('training/runs/v2/candidates/e5_tfidf/bundle')
    expected_version: str = 'svo-e2a46f504b19'
    db_path: Path = Path('app/server/data/observatory.sqlite')
    mode: str = 'local_demo'
    credentials: dict[str, str] = field(default_factory=dict, repr=False)  # alias -> key
    allowed_origins: tuple[str, ...] = ()
    queue_capacity: int = 32
    body_limit: int = 65536
    shutdown_seconds: float = 25
    min_free_bytes: int = 16 * 1024 * 1024

    def __post_init__(self):
        if self.mode not in ('local_demo', 'authenticated'):
            raise ValueError('Invalid SVO_MODE')
        if self.mode == 'authenticated' and not self.credentials:
            raise ValueError('Authenticated mode requires SVO_CREDENTIALS_JSON')
        if not isinstance(self.credentials, dict) or any(
            not isinstance(a, str) or not a.strip() or len(a) > 80
            or not isinstance(k, str) or len(k) < 32 or not k.isascii()
            for a, k in self.credentials.items()
        ) or len(set(self.credentials.values())) != len(self.credentials):
            raise ValueError('Credentials require unique ASCII keys of at least 32 characters and analyst aliases')
        if not self.expected_version or not 1 <= self.queue_capacity <= 1024:
            raise ValueError('Invalid expected version or queue capacity')
        if self.body_limit < 1 or self.shutdown_seconds <= 0 or self.min_free_bytes < 0:
            raise ValueError('Invalid resource limits')
        if any(not x.startswith(('http://', 'https://')) or '*' in x for x in self.allowed_origins):
            raise ValueError('CORS origins must be explicit HTTP(S) origins')

    @classmethod
    def from_env(cls):
        try:
            return cls(
                model_dir=Path(os.getenv('SVO_MODEL_DIR', 'training/runs/v2/candidates/e5_tfidf/bundle')),
                expected_version=os.getenv('SVO_EXPECTED_MODEL_VERSION', 'svo-e2a46f504b19'),
                db_path=Path(os.getenv('SVO_DB_PATH', 'app/server/data/observatory.sqlite')),
                mode=os.getenv('SVO_MODE', 'local_demo'),
                credentials=json.loads(os.getenv('SVO_CREDENTIALS_JSON', '{}')),
                allowed_origins=tuple(x.strip() for x in os.getenv('SVO_ALLOWED_ORIGINS', '').split(',') if x.strip()),
                queue_capacity=int(os.getenv('SVO_QUEUE_CAPACITY', '32')),
            )
        except (ValueError, TypeError):
            raise ValueError('Invalid server configuration; check SVO environment settings') from None
