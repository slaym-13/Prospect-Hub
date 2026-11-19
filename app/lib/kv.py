"""Where the app's JSON documents live when DATABASE_URL is set: one Postgres table.

The app keeps a handful of whole documents ("db" for companies and notes, "users" for
accounts, "secret" for the signing key). Without DATABASE_URL they are files in
DATA_DIR, as before; with it, each is a row here, so they survive a host such as
Vercel wiping its disk, and every server instance sees the same data.

Each row carries a version that goes up on every write, so an instance can tell
cheaply whether its copy is stale.

DATABASE_URL=memory:// keeps the rows in this process only. The tests use it.
"""
import os
import threading

TABLE = 'prospect_hub.docs'
_lock = threading.RLock()
_conn = None
_ready = False
_memory = {}


def url():
    return os.environ.get('DATABASE_URL') or ''


def enabled():
    return bool(url())


def _is_memory():
    return url().startswith('memory:')


def _connect():
    import psycopg
    # prepare_threshold=None: Supabase's transaction pooler (port 6543) cannot keep
    # prepared statements between calls.
    return psycopg.connect(url(), autocommit=True, prepare_threshold=None, connect_timeout=10)


def _setup(cur):
    # A schema of its own, not "public": Supabase publishes "public" through its REST
    # API. Row level security with no policies shuts that door too, in case the schema
    # is ever exposed. The connection string's role owns the table and is not affected.
    cur.execute('CREATE SCHEMA IF NOT EXISTS prospect_hub')
    cur.execute(f'CREATE TABLE IF NOT EXISTS {TABLE} ('
                'name text PRIMARY KEY, data text NOT NULL, version bigint NOT NULL DEFAULT 1, '
                'updated_at timestamptz NOT NULL DEFAULT now())')
    cur.execute(f'ALTER TABLE {TABLE} ENABLE ROW LEVEL SECURITY')


def _run(sql, params=()):
    """One statement on the shared connection, reconnecting once if it went stale."""
    global _conn, _ready
    import psycopg
    with _lock:
        for attempt in (1, 2):
            try:
                if _conn is None or _conn.closed:
                    _conn = _connect()
                with _conn.cursor() as cur:
                    if not _ready:
                        _setup(cur)
                        _ready = True
                    cur.execute(sql, params)
                    return cur.fetchone() if cur.description else None
            except psycopg.OperationalError:
                # A warm serverless instance can hold a connection the pooler has closed.
                try:
                    if _conn is not None:
                        _conn.close()
                finally:
                    _conn = None
                if attempt == 2:
                    raise


def read(name):
    """(text, version) of a document, or (None, 0) if it was never written."""
    if _is_memory():
        with _lock:
            return _memory.get(name, (None, 0))
    row = _run(f'SELECT data, version FROM {TABLE} WHERE name = %s', (name,))
    return (row[0], row[1]) if row else (None, 0)


def version(name):
    if _is_memory():
        with _lock:
            return _memory.get(name, (None, 0))[1]
    row = _run(f'SELECT version FROM {TABLE} WHERE name = %s', (name,))
    return row[0] if row else 0


def write(name, text):
    """Store a document (JSON text) and return its new version."""
    if _is_memory():
        with _lock:
            v = _memory.get(name, (None, 0))[1] + 1
            _memory[name] = (text, v)
            return v
    row = _run(f'INSERT INTO {TABLE} AS d (name, data) VALUES (%s, %s) '
               'ON CONFLICT (name) DO UPDATE SET data = EXCLUDED.data, version = d.version + 1, '
               'updated_at = now() RETURNING d.version', (name, text))
    return row[0]


def insert_if_missing(name, text):
    """Store a document only if none exists yet; return whichever text is stored."""
    if _is_memory():
        with _lock:
            if name not in _memory:
                _memory[name] = (text, 1)
            return _memory[name][0]
    _run(f'INSERT INTO {TABLE} (name, data) VALUES (%s, %s) ON CONFLICT (name) DO NOTHING', (name, text))
    return read(name)[0]
