"""Run on the host or inside the container; SQLite backup includes committed WAL data."""
import argparse
from pathlib import Path
import sqlite3

parser = argparse.ArgumentParser()
parser.add_argument('source', type=Path)
parser.add_argument('destination', type=Path)
args = parser.parse_args()
if not args.source.is_file():
    parser.error('Source database does not exist')
# Exclusive creation prevents accidental replacement of existing backups.
with args.destination.open('xb'):
    pass
with sqlite3.connect(args.source.resolve().as_uri()+'?mode=ro', uri=True) as source:
    with sqlite3.connect(args.destination) as target:
        source.backup(target)
        assert target.execute('PRAGMA integrity_check').fetchone()[0] == 'ok'
print('Backup complete')
