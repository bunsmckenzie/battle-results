import tempfile
import unittest
import shutil
from pathlib import Path
from unittest.mock import patch
from batch_ingestion import battle_folders, preflight_batch, ingest_batch
from battle_processor import load_battle

FIX = Path(__file__).parent / "fixtures"

class BatchIngestionTests(unittest.TestCase):
    def test_only_immediate_subfolders_are_battles_and_sorted(self):
        with tempfile.TemporaryDirectory() as td:
            root=Path(td); (root/'zeta').mkdir(); (root/'Alpha').mkdir(); (root/'loose.jpg').write_bytes(b'x')
            self.assertEqual([p.name for p in battle_folders(root)], ['Alpha','zeta'])

    def test_preflight_reports_ready_and_invalid_without_processing(self):
        with tempfile.TemporaryDirectory() as td:
            root=Path(td); good=root/'good'; bad=root/'bad'; good.mkdir(); bad.mkdir()
            def resolve(folder):
                if Path(folder).name == 'bad': raise ValueError('missing heroes image')
                return {'outcome':'o','heroes':'h','ratios_bonuses':'r'}
            with patch('batch_ingestion.resolve_battle_images', side_effect=resolve), patch('batch_ingestion.extract_battle_identity', return_value=None), patch('batch_ingestion.extract_battle_metadata'), patch('batch_ingestion.process_battle') as proc:
                items=preflight_batch(root)
            self.assertEqual([(i.folder.name,i.status) for i in items], [('bad','INVALID'),('good','READY')])
            proc.assert_not_called()

    def test_ingest_continues_after_bad_sibling(self):
        with tempfile.TemporaryDirectory() as td:
            root=Path(td); (root/'01-good').mkdir(); (root/'02-bad').mkdir(); (root/'03-good').mkdir()
            def resolve(folder):
                if Path(folder).name == '02-bad': raise ValueError('duplicate outcome')
                return {'outcome':f'{folder}/o.jpg','heroes':f'{folder}/h.jpg','ratios_bonuses':f'{folder}/r.jpg'}
            keys=iter(['B000001','B000002'])
            with patch('batch_ingestion.resolve_battle_images', side_effect=resolve), patch('batch_ingestion.process_battle', side_effect=lambda *a,**k: next(keys)):
                items=ingest_batch(root)
            self.assertEqual([(i.folder.name,i.status,i.battle_key) for i in items], [('01-good','SAVED','B000001'),('02-bad','FAILED',None),('03-good','SAVED','B000002')])


    def test_real_batch_persists_step87_troop_levels(self):
        with tempfile.TemporaryDirectory() as td:
            root=Path(td); parent=root/'batch'; battle=parent/'001'; battle.mkdir(parents=True)
            shutil.copy2(FIX/'outcome.jpg', battle/'alpha.jpg')
            shutil.copy2(FIX/'herocomparison.jpg', battle/'beta.jpg')
            shutil.copy2(FIX/'ratiosbonuses.jpg', battle/'gamma.jpg')
            db_path=root/'batch.sqlite3'
            items=ingest_batch(parent, db_path=db_path)
            self.assertEqual([(i.status,i.battle_key) for i in items], [('SAVED','B000001')])
            data=load_battle('B000001', db_path=db_path)
            ratios={(side,troop):(ratio,present,level,tg) for side,troop,ratio,present,level,tg in data['ratios']}
            self.assertEqual(ratios[('attacker','infantry')], (48.93,1,10.9,7))
            self.assertEqual(ratios[('defender','archer')], (0.0,0,None,None))

    def test_real_batch_accepts_scrambled_fullscreen_count_view(self):
        with tempfile.TemporaryDirectory() as td:
            root=Path(td); parent=root/'batch'; battle=parent/'battle2'; battle.mkdir(parents=True)
            # Deliberately copy in a filename/order that carries no domain meaning.
            shutil.copy2(FIX/'full_heroes.jpg', battle/'Screenshot_155151.jpg')
            shutil.copy2(FIX/'full_outcome.jpg', battle/'Screenshot_155241.jpg')
            shutil.copy2(FIX/'full_ratios_counts.jpg', battle/'Screenshot_155247.jpg')
            preflight=preflight_batch(parent)
            self.assertEqual([(i.status,i.error) for i in preflight],[('READY',None)])
            db_path=root/'batch.sqlite3'
            items=ingest_batch(parent,db_path=db_path)
            self.assertEqual([(i.status,i.battle_key) for i in items],[('SAVED','B000001')])
            data=load_battle('B000001',db_path=db_path)
            outcomes={r[0]:r[1:] for r in data['outcomes']}
            self.assertEqual(outcomes['attacker'],(-75044180,1588832,0,556103,1032729,0))
            self.assertEqual(outcomes['defender'],(-31304981,1633832,0,239587,444921,949324))
            ratios={(side,troop):(ratio,present,level,tg) for side,troop,ratio,present,level,tg in data['ratios']}
            self.assertEqual(ratios[('attacker','infantry')],(49.0,1,11.0,8))
            self.assertEqual(ratios[('defender','archer')],(49.63,1,10.5,7))
            self.assertEqual(data['battle'][8:11],('Meridian','Al KaabiUAE','DEFEAT'))

    def test_preflight_finds_duplicate_in_step91_database_without_writing_migration(self):
        with tempfile.TemporaryDirectory() as td:
            root=Path(td); parent=root/'batch'; battle=parent/'battle2'; battle.mkdir(parents=True)
            shutil.copy2(FIX/'full_heroes.jpg', battle/'a.jpg')
            shutil.copy2(FIX/'full_outcome.jpg', battle/'b.jpg')
            shutil.copy2(FIX/'full_ratios_counts.jpg', battle/'c.jpg')
            db_path=root/'old.sqlite3'
            import db
            from contextlib import closing
            with closing(db.connect(db_path)) as conn:
                conn.execute('CREATE TABLE schema_migrations (version TEXT PRIMARY KEY, applied_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP)')
                for migration in sorted(db.MIGRATIONS_DIR.glob('*.sql'))[:4]:
                    conn.executescript(migration.read_text(encoding='utf-8'))
                    conn.execute('INSERT INTO schema_migrations(version) VALUES (?)',(migration.name,))
                conn.execute('''INSERT INTO battles(battle_id,battle_key,outcome_image) VALUES (1,'B000001',?)''',(str(FIX/'full_outcome.jpg'),))
                conn.commit()
            items=preflight_batch(parent,db_path=db_path)
            self.assertEqual([(i.status,i.battle_key) for i in items],[('DUPLICATE','B000001')])
            with closing(db.connect(db_path)) as conn:
                columns={r[1] for r in conn.execute('PRAGMA table_info(battles)')}
                self.assertNotIn('battle_identity',columns)  # dry-run made no schema changes

    def test_repeat_fullscreen_batch_is_reported_duplicate_and_not_inserted(self):
        with tempfile.TemporaryDirectory() as td:
            root=Path(td); parent=root/'batch'; battle=parent/'battle2'; battle.mkdir(parents=True)
            shutil.copy2(FIX/'full_heroes.jpg', battle/'a.jpg')
            shutil.copy2(FIX/'full_outcome.jpg', battle/'b.jpg')
            shutil.copy2(FIX/'full_ratios_counts.jpg', battle/'c.jpg')
            db_path=root/'batch.sqlite3'
            first=ingest_batch(parent,db_path=db_path)
            self.assertEqual([(i.status,i.battle_key) for i in first],[('SAVED','B000001')])
            dry=preflight_batch(parent,db_path=db_path)
            self.assertEqual([(i.status,i.battle_key) for i in dry],[('DUPLICATE','B000001')])
            second=ingest_batch(parent,db_path=db_path)
            self.assertEqual([(i.status,i.battle_key) for i in second],[('DUPLICATE','B000001')])
            import db
            from contextlib import closing
            with closing(db.connect(db_path)) as conn:
                self.assertEqual(conn.execute('SELECT COUNT(*) FROM battles').fetchone()[0],1)

    def test_preflight_detects_same_identity_twice_within_one_batch(self):
        with tempfile.TemporaryDirectory() as td:
            root=Path(td); parent=root/'batch'
            for name in ('one','two'):
                battle=parent/name; battle.mkdir(parents=True)
                shutil.copy2(FIX/'full_heroes.jpg', battle/'h.jpg')
                shutil.copy2(FIX/'full_outcome.jpg', battle/'o.jpg')
                shutil.copy2(FIX/'full_ratios_counts.jpg', battle/'r.jpg')
            missing_db=root/'does-not-exist.sqlite3'
            items=preflight_batch(parent,db_path=missing_db)
            self.assertFalse(missing_db.exists())
            self.assertEqual(items[0].status,'READY')
            self.assertEqual(items[1].status,'DUPLICATE')
            self.assertEqual(items[1].duplicate_of,'one')

    def test_empty_parent_rejected(self):
        with tempfile.TemporaryDirectory() as td:
            with self.assertRaisesRegex(ValueError, 'No battle subfolders'):
                preflight_batch(td)

if __name__ == '__main__': unittest.main()
