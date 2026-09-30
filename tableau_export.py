"""Export Step 12 reporting views to Tableau-friendly CSV files."""
from __future__ import annotations

import csv
from contextlib import closing
from dataclasses import dataclass
from pathlib import Path
import tempfile

import db
from reporting_views import REPORTING_VIEWS


EXPORT_FILES = {
    'summary': 'battle_summary.csv',
    'troops': 'battle_troops.csv',
    'bonuses': 'battle_bonuses.csv',
    'heroes': 'battle_heroes.csv',
}

# Stable ordering makes diffs, validation, and Tableau refreshes predictable.
ORDER_BY = {
    'summary': 'battle_id',
    'troops': 'battle_id, side, troop_type',
    'bonuses': 'battle_id, side, troop_type, stat',
    'heroes': 'battle_id, side, role, slot',
}


@dataclass(frozen=True)
class ExportResult:
    name: str
    view: str
    path: Path
    row_count: int


def _write_csv_atomic(path: Path, columns: list[str], rows) -> None:
    """Write a CSV completely, then atomically replace the prior export."""
    path.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile(
        mode='w',
        encoding='utf-8-sig',
        newline='',
        dir=path.parent,
        prefix=f'.{path.name}.',
        suffix='.tmp',
        delete=False,
    ) as tmp:
        temp_path = Path(tmp.name)
        writer = csv.writer(tmp, lineterminator='\n')
        writer.writerow(columns)
        for row in rows:
            # csv.writer renders None as an empty field, which Tableau treats as null.
            writer.writerow(row)
    temp_path.replace(path)


def export_tableau(output_dir, db_path=None) -> list[ExportResult]:
    """Export all reporting views to stable CSV filenames.

    Existing CSVs are replaced only after each new file is fully written.
    The database remains read-only apart from applying any pending schema
    migrations needed to create the reporting views.
    """
    output = Path(output_dir)
    output.mkdir(parents=True, exist_ok=True)
    db.init_db(db_path)

    results: list[ExportResult] = []
    with closing(db.connect(db_path)) as conn:
        for name, view in REPORTING_VIEWS.items():
            cur = conn.execute(f'SELECT * FROM {view} ORDER BY {ORDER_BY[name]}')
            columns = [d[0] for d in cur.description]
            rows = cur.fetchall()
            path = output / EXPORT_FILES[name]
            _write_csv_atomic(path, columns, rows)
            results.append(ExportResult(name, view, path, len(rows)))
    return results
