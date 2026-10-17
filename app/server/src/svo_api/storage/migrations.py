SCHEMA_VERSION = 1


def migrate(db):
    version = db.execute('PRAGMA user_version').fetchone()[0]
    if version not in (0, SCHEMA_VERSION):
        raise ValueError('Unsupported database schema version')
    db.execute('PRAGMA busy_timeout=2000')
    db.execute('PRAGMA synchronous=FULL')
    with db:
        db.execute('CREATE TABLE IF NOT EXISTS review_requests ('
                   'review_id TEXT PRIMARY KEY, fingerprint TEXT NOT NULL, '
                   'audit_id INTEGER NOT NULL, response TEXT NOT NULL)')
        db.execute('CREATE INDEX IF NOT EXISTS events_version_seq ON events(version, seq)')
        db.execute('CREATE INDEX IF NOT EXISTS clusters_version ON clusters(version, id)')
        db.execute('CREATE INDEX IF NOT EXISTS reviews_cluster ON reviews(version, cluster_id, id)')
        db.execute(f'PRAGMA user_version={SCHEMA_VERSION}')
    # Verify writable storage, even when no migration is necessary.
    db.execute('BEGIN IMMEDIATE')
    db.execute('UPDATE review_requests SET fingerprint=fingerprint WHERE 0')
    db.rollback()
