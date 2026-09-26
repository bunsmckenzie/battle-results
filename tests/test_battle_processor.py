import tempfile, unittest
from pathlib import Path
from contextlib import closing
import db
from battle_processor import normalize_ratios, process_battle, load_battle
from percent_reader import PercentReading

ROOT=Path(__file__).resolve().parent
FIX=ROOT/'fixtures'

class BattleProcessorTests(unittest.TestCase):
    def test_missing_ratio_is_zero_and_marked_absent(self):
        x={
          'attacker.ratio.slot1':{'troop_type':'infantry','reading':PercentReading(60,1)},
          'attacker.ratio.slot2':{'troop_type':'cavalry','reading':PercentReading(40,1)},
          'defender.ratio.slot1':{'troop_type':'infantry','reading':PercentReading(100,1)},
        }
        rows=normalize_ratios(x)
        self.assertEqual(len(rows),6)
        self.assertIn(('defender','archer',0.0,0,None),rows)

    def test_process_fixture_persists_complete_battle(self):
        with tempfile.TemporaryDirectory() as td:
            path=Path(td)/'b.sqlite3'
            key=process_battle(FIX/'outcome.jpg',FIX/'herocomparison.jpg',FIX/'ratiosbonuses.jpg',path)
            self.assertEqual(key,'B000001')
            b=load_battle(key,path)
            self.assertEqual(len(b['outcomes']),2); self.assertEqual(len(b['ratios']),6)
            self.assertEqual(len(b['bonuses']),24); self.assertEqual(len(b['heroes']),6)
            self.assertIn(('defender','archer',0.0,0),b['ratios'])
            self.assertTrue(all(r[1]=='lead' for r in b['heroes']))

    def test_battle_keys_increment(self):
        with tempfile.TemporaryDirectory() as td:
            path=Path(td)/'b.sqlite3'
            a=process_battle(FIX/'outcome.jpg',FIX/'herocomparison.jpg',FIX/'ratiosbonuses.jpg',path)
            b=process_battle(FIX/'outcome.jpg',FIX/'herocomparison.jpg',FIX/'ratiosbonuses.jpg',path)
            self.assertEqual((a,b),('B000001','B000002'))

if __name__=='__main__': unittest.main()
