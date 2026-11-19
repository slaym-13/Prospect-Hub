"""Copy the local data files into the Postgres database named by DATABASE_URL.

    DATABASE_URL="postgresql://..." python scripts/upload_to_database.py [--force]

Uploads data/db.json (companies, notes, settings) and data/users.json (accounts). It
refuses to replace what the database already holds unless --force is given.
"""
import json
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from dotenv import load_dotenv  # noqa: E402

load_dotenv(os.path.join(ROOT, '.env'))

from lib import kv  # noqa: E402

DATA_DIR = os.environ.get('DATA_DIR') or os.path.join(ROOT, 'data')
DOCS = {'db': 'db.json', 'users': 'users.json'}


def main():
    force = '--force' in sys.argv[1:]
    if not kv.enabled() or kv.url().startswith('memory:'):
        print('Set DATABASE_URL to the Supabase connection string first.', file=sys.stderr)
        sys.exit(1)
    for name, file in DOCS.items():
        path = os.path.join(DATA_DIR, file)
        if not os.path.exists(path):
            print(f'{file}: not found, skipped')
            continue
        with open(path, encoding='utf-8') as f:
            text = f.read()
        json.loads(text)   # refuse to upload a broken file
        if kv.version(name) and not force:
            print(f'{file}: the database already has "{name}". Run again with --force to replace it.')
            continue
        v = kv.write(name, text)
        print(f'{file}: uploaded (version {v})')


if __name__ == '__main__':
    main()
