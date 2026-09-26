import sqlite3
from contextlib import closing
import tempfile
import unittest
from pathlib import Path

import db


class DatabaseTests(unittest.TestCase):
    def setUp(self):
        self.tempdir = tempfile.TemporaryDirectory()
        self.db_path = Path(self.tempdir.name) / 'test.sqlite3'

    def tearDown(self):
        self.tempdir.cleanup()

    def test_init_creates_expected_schema_and_records_migration(self):
        db.init_db(self.db_path)
        with closing(db.connect(self.db_path)) as conn:
            tables = {
                row[0]
                for row in conn.execute(
                    "SELECT name FROM sqlite_master WHERE type='table'"
                )
            }
            expected = {
                'schema_migrations', 'heroes', 'battles', 'battle_outcomes',
                'troop_ratios', 'troop_bonuses', 'battle_heroes'
            }
            self.assertTrue(expected.issubset(tables))
            migrations = conn.execute(
                'SELECT version FROM schema_migrations ORDER BY version'
            ).fetchall()
            self.assertEqual(migrations, [('001_initial_schema.sql',), ('002_battle_relationship_model.sql',), ('003_hero_role_value_contract.sql',)])

    def test_init_is_idempotent(self):
        db.init_db(self.db_path)
        db.init_db(self.db_path)
        with closing(db.connect(self.db_path)) as conn:
            count = conn.execute('SELECT COUNT(*) FROM schema_migrations').fetchone()[0]
            self.assertEqual(count, 3)

    def test_seed_loads_22_heroes_and_is_idempotent(self):
        db.init_db(self.db_path)
        db.seed_heroes(self.db_path)
        db.seed_heroes(self.db_path)
        with closing(db.connect(self.db_path)) as conn:
            self.assertEqual(conn.execute('SELECT COUNT(*) FROM heroes').fetchone()[0], 22)
            self.assertEqual(
                conn.execute('SELECT name FROM heroes WHERE hero_id = 1').fetchone()[0],
                'Yang',
            )

    def test_foreign_keys_and_join_value_constraint_are_enforced(self):
        db.init_db(self.db_path)
        db.seed_heroes(self.db_path)
        with closing(db.connect(self.db_path)) as conn:
            conn.execute("INSERT INTO battles(source_image) VALUES ('fixture.jpg')")
            battle_id = conn.execute('SELECT last_insert_rowid()').fetchone()[0]
            with self.assertRaises(sqlite3.IntegrityError):
                conn.execute(
                    "INSERT INTO battle_heroes(battle_id, side, role, slot, hero_id, join_value) VALUES (?, 'attacker', 'lead', 1, 999, 10)",
                    (battle_id,),
                )
            with self.assertRaises(sqlite3.IntegrityError):
                conn.execute(
                    "INSERT INTO battle_heroes(battle_id, side, role, slot, hero_id, join_value) VALUES (?, 'attacker', 'lead', 1, 1, 11)",
                    (battle_id,),
                )

    def test_connections_close_before_database_file_removal(self):
        db.init_db(self.db_path)
        db.seed_heroes(self.db_path)
        with closing(db.connect(self.db_path)) as conn:
            self.assertEqual(conn.execute('SELECT COUNT(*) FROM heroes').fetchone()[0], 22)
        # On Windows an open SQLite connection prevents this unlink operation.
        self.db_path.unlink()
        self.assertFalse(self.db_path.exists())

    def test_seed_before_init_has_clear_error(self):
        with self.assertRaisesRegex(RuntimeError, 'not initialized'):
            db.seed_heroes(self.db_path)


if __name__ == '__main__':
    unittest.main()
