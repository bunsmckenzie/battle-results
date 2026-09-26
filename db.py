from pathlib import Path
import sqlite3

DB_PATH = Path('battle_data.sqlite3')
MIGRATIONS_DIR = Path('migrations')


def connect():
    conn = sqlite3.connect(DB_PATH)
    conn.execute('PRAGMA foreign_keys = ON')
    return conn


def init_db():
    conn = connect()
    try:
        for path in sorted(MIGRATIONS_DIR.glob('*.sql')):
            conn.executescript(path.read_text(encoding='utf-8'))
        conn.commit()
    finally:
        conn.close()


def seed_heroes():
    conn = connect()
    try:
        conn.executescript(Path('heroes_seed.sql').read_text(encoding='utf-8'))
        conn.commit()
    finally:
        conn.close()
