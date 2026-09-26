from pathlib import Path
from contextlib import closing
import sqlite3

BASE_DIR = Path(__file__).resolve().parent
DB_PATH = BASE_DIR / 'battle_data.sqlite3'
MIGRATIONS_DIR = BASE_DIR / 'migrations'
HEROES_SEED_PATH = BASE_DIR / 'heroes_seed.sql'


def connect(db_path=None):
    path = Path(db_path) if db_path is not None else DB_PATH
    conn = sqlite3.connect(path)
    try:
        conn.execute('PRAGMA foreign_keys = ON')
    except BaseException:
        conn.close()
        raise
    return conn


def _migration_files():
    if not MIGRATIONS_DIR.is_dir():
        raise FileNotFoundError(f'Migrations directory not found: {MIGRATIONS_DIR}')
    paths = sorted(MIGRATIONS_DIR.glob('*.sql'))
    if not paths:
        raise RuntimeError(f'No SQL migrations found in: {MIGRATIONS_DIR}')
    return paths


def init_db(db_path=None):
    with closing(connect(db_path)) as conn:
        # Bootstrap only the migration ledger; all application tables belong in migrations.
        conn.execute('''
            CREATE TABLE IF NOT EXISTS schema_migrations (
                version TEXT PRIMARY KEY,
                applied_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        applied = {
            row[0]
            for row in conn.execute('SELECT version FROM schema_migrations')
        }
        for path in _migration_files():
            version = path.name
            if version in applied:
                continue
            with conn:
                conn.executescript(path.read_text(encoding='utf-8'))
                conn.execute(
                    'INSERT INTO schema_migrations(version) VALUES (?)',
                    (version,),
                )


def seed_heroes(db_path=None):
    if not HEROES_SEED_PATH.is_file():
        raise FileNotFoundError(f'Hero seed file not found: {HEROES_SEED_PATH}')
    with closing(connect(db_path)) as conn:
        # Give a clearer error than SQLite's generic "no such table" message.
        exists = conn.execute(
            "SELECT 1 FROM sqlite_master WHERE type='table' AND name='heroes'"
        ).fetchone()
        if not exists:
            raise RuntimeError('Database is not initialized. Run `python app.py init-db` first.')
        with conn:
            conn.executescript(HEROES_SEED_PATH.read_text(encoding='utf-8'))
