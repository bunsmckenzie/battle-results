from contextlib import closing
from pathlib import Path
import tempfile
import unittest

import db
from battle_processor import process_battle, add_joiner
from reporting_views import preview_view

FIX = Path(__file__).parent / 'fixtures'


class ReportingViewsTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tempdir = tempfile.TemporaryDirectory()
        cls.db_path = Path(cls.tempdir.name) / 'reporting.sqlite3'
        process_battle(
            FIX / 'outcome.jpg',
            FIX / 'herocomparison.jpg',
            FIX / 'ratiosbonuses.jpg',
            cls.db_path,
        )
        add_joiner('B000001', 'attacker', 'Sophia', cls.db_path)

    @classmethod
    def tearDownClass(cls):
        cls.tempdir.cleanup()

    def test_four_reporting_views_exist(self):
        with closing(db.connect(self.db_path)) as conn:
            views = {
                row[0] for row in conn.execute(
                    "SELECT name FROM sqlite_master WHERE type='view'"
                )
            }
        self.assertTrue({
            'vw_battle_summary', 'vw_battle_troops',
            'vw_battle_bonuses', 'vw_battle_heroes'
        }.issubset(views))

    def test_summary_is_one_row_per_battle_with_wide_analysis_fields(self):
        with closing(db.connect(self.db_path)) as conn:
            conn.row_factory = __import__('sqlite3').Row
            row = conn.execute(
                "SELECT * FROM vw_battle_summary WHERE battle_key='B000001'"
            ).fetchone()
            self.assertEqual(conn.execute('SELECT COUNT(*) FROM vw_battle_summary').fetchone()[0], 1)
        self.assertEqual(row['attacker_name'], 'Meridian')
        self.assertEqual(row['defender_name'], 'Al KaabiUAE')
        self.assertEqual(row['result'], 'DEFEAT')
        self.assertEqual(row['attacker_power'], -75044045)
        self.assertAlmostEqual(row['attacker_infantry_ratio'], 48.93, places=2)
        self.assertAlmostEqual(row['attacker_infantry_troop_level'], 10.9, places=1)
        self.assertEqual(row['attacker_infantry_tg_level'], 7)
        self.assertEqual(row['defender_archer_present'], 0)
        self.assertIsNone(row['defender_archer_troop_level'])
        self.assertIsNone(row['defender_archer_tg_level'])

    def test_troop_view_has_six_rows_per_battle(self):
        with closing(db.connect(self.db_path)) as conn:
            rows = conn.execute(
                "SELECT side,troop_type,ratio,was_present,troop_level,tg_level "
                "FROM vw_battle_troops WHERE battle_key='B000001'"
            ).fetchall()
        self.assertEqual(len(rows), 6)
        self.assertIn(('defender', 'archer', 0.0, 0, None, None), rows)

    def test_bonus_view_has_twenty_four_rows_per_battle(self):
        with closing(db.connect(self.db_path)) as conn:
            count = conn.execute(
                "SELECT COUNT(*) FROM vw_battle_bonuses WHERE battle_key='B000001'"
            ).fetchone()[0]
            value = conn.execute(
                "SELECT value FROM vw_battle_bonuses "
                "WHERE battle_key='B000001' AND side='attacker' "
                "AND troop_type='infantry' AND stat='attack'"
            ).fetchone()[0]
        self.assertEqual(count, 24)
        self.assertAlmostEqual(value, 2109.0, places=1)

    def test_hero_view_includes_leads_and_name_only_joiners(self):
        with closing(db.connect(self.db_path)) as conn:
            rows = conn.execute(
                "SELECT side,role,slot,hero_name,join_value "
                "FROM vw_battle_heroes WHERE battle_key='B000001'"
            ).fetchall()
        self.assertEqual(len(rows), 7)
        self.assertIn(('attacker', 'lead', 1, 'Charles', 10), rows)
        self.assertIn(('attacker', 'joiner', 1, 'Sophia', None), rows)

    def test_preview_view_returns_columns_and_honors_limit(self):
        view, columns, rows = preview_view('troops', 2, self.db_path)
        self.assertEqual(view, 'vw_battle_troops')
        self.assertIn('battle_key', columns)
        self.assertIn('troop_level', columns)
        self.assertEqual(len(rows), 2)


if __name__ == '__main__':
    unittest.main()
