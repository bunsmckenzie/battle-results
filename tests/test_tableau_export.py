from pathlib import Path
import csv
import tempfile
import unittest

from battle_processor import process_battle, add_joiner
from tableau_export import export_tableau

FIX = Path(__file__).parent / 'fixtures'


class TableauExportTests(unittest.TestCase):
    def setUp(self):
        self.tempdir = tempfile.TemporaryDirectory()
        self.root = Path(self.tempdir.name)
        self.db_path = self.root / 'export.sqlite3'
        self.out = self.root / 'tableau'
        process_battle(
            FIX / 'outcome.jpg',
            FIX / 'herocomparison.jpg',
            FIX / 'ratiosbonuses.jpg',
            self.db_path,
        )
        add_joiner('B000001', 'attacker', 'Sophia', self.db_path)

    def tearDown(self):
        self.tempdir.cleanup()

    def _read(self, name):
        with (self.out / name).open('r', encoding='utf-8-sig', newline='') as f:
            return list(csv.DictReader(f))

    def test_exports_four_stable_csv_files_with_expected_grain(self):
        results = export_tableau(self.out, self.db_path)
        self.assertEqual([r.name for r in results], ['summary','troops','bonuses','heroes'])
        self.assertEqual({r.path.name for r in results}, {
            'battle_summary.csv','battle_troops.csv','battle_bonuses.csv','battle_heroes.csv'
        })
        self.assertEqual(len(self._read('battle_summary.csv')), 1)
        self.assertEqual(len(self._read('battle_troops.csv')), 6)
        self.assertEqual(len(self._read('battle_bonuses.csv')), 24)
        self.assertEqual(len(self._read('battle_heroes.csv')), 7)

    def test_summary_contains_tableau_analysis_fields(self):
        row = self._read_after_export('battle_summary.csv')[0]
        self.assertEqual(row['battle_key'], 'B000001')
        self.assertEqual(row['attacker_name'], 'Meridian')
        self.assertEqual(row['defender_name'], 'Al KaabiUAE')
        self.assertEqual(row['result'], 'DEFEAT')
        self.assertEqual(row['attacker_infantry_ratio'], '48.93')

    def _read_after_export(self, name):
        export_tableau(self.out, self.db_path)
        return self._read(name)

    def test_nulls_are_exported_as_empty_fields(self):
        rows = self._read_after_export('battle_troops.csv')
        archer = next(r for r in rows if r['side']=='defender' and r['troop_type']=='archer')
        self.assertEqual(archer['was_present'], '0')
        self.assertEqual(archer['troop_level'], '')
        self.assertEqual(archer['tg_level'], '')

    def test_export_overwrites_existing_files_instead_of_appending(self):
        export_tableau(self.out, self.db_path)
        summary = self.out / 'battle_summary.csv'
        summary.write_text('stale-data\n', encoding='utf-8')
        export_tableau(self.out, self.db_path)
        rows = self._read('battle_summary.csv')
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]['battle_key'], 'B000001')
        self.assertNotIn('stale-data', summary.read_text(encoding='utf-8-sig'))

    def test_empty_database_still_exports_headers(self):
        empty_db = self.root / 'empty.sqlite3'
        empty_out = self.root / 'empty_export'
        results = export_tableau(empty_out, empty_db)
        self.assertTrue(all(r.row_count == 0 for r in results))
        with (empty_out/'battle_summary.csv').open('r', encoding='utf-8-sig', newline='') as f:
            reader = csv.reader(f)
            header = next(reader)
            self.assertIn('battle_key', header)
            self.assertEqual(list(reader), [])


if __name__ == '__main__':
    unittest.main()
