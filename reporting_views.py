"""Small read-only helpers for the Step 12 Tableau/reporting views."""
from __future__ import annotations
from contextlib import closing
import db

REPORTING_VIEWS = {
    'summary': 'vw_battle_summary',
    'troops': 'vw_battle_troops',
    'bonuses': 'vw_battle_bonuses',
    'heroes': 'vw_battle_heroes',
}


def preview_view(name: str, limit: int = 10, db_path=None):
    if name not in REPORTING_VIEWS:
        raise ValueError(f'Unknown reporting view: {name}')
    if limit < 1:
        raise ValueError('limit must be at least 1')
    db.init_db(db_path)
    view = REPORTING_VIEWS[name]
    with closing(db.connect(db_path)) as conn:
        cur = conn.execute(f'SELECT * FROM {view} LIMIT ?', (limit,))
        columns = [d[0] for d in cur.description]
        rows = cur.fetchall()
    return view, columns, rows
