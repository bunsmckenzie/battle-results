import tempfile
import unittest
from pathlib import Path
import sqlite3
import db
from contextlib import closing
from battle_processor import add_joiner, remove_joiner, load_battle

class JoinerTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory(); self.path=Path(self.tmp.name)/'test.sqlite3'
        db.init_db(self.path); db.seed_heroes(self.path)
        with closing(db.connect(self.path)) as c:
            c.execute("INSERT INTO battles(battle_id,battle_key) VALUES (1,'B000001')")
            hid=c.execute("SELECT hero_id FROM heroes WHERE name='Ava'").fetchone()[0]
            c.execute("INSERT INTO battle_heroes(battle_id,side,role,slot,hero_id,join_value) VALUES (1,'attacker','lead',1,?,10)",(hid,)); c.commit()
    def tearDown(self): self.tmp.cleanup()
    def test_add_and_remove_joiner(self):
        slot,name=add_joiner('B000001','attacker','Charles',self.path)
        self.assertEqual((slot,name),(1,'Charles'))
        heroes=load_battle('B000001',self.path)['heroes']
        self.assertIn(('attacker','joiner',1,'Charles',None),heroes)
        self.assertIn(('attacker','lead',1,'Ava',10),heroes)
        self.assertEqual(remove_joiner('B000001','attacker',1,self.path),'Charles')
        self.assertNotIn(('attacker','joiner',1,'Charles',None),load_battle('B000001',self.path)['heroes'])
    def test_slots_are_per_side(self):
        self.assertEqual(add_joiner('B000001','attacker','Charles',self.path)[0],1)
        self.assertEqual(add_joiner('B000001','attacker','Sophia',self.path)[0],2)
        self.assertEqual(add_joiner('B000001','defender','Charles',self.path)[0],1)
    def test_reject_unknown_hero(self):
        with self.assertRaises(ValueError): add_joiner('B000001','attacker','Not A Hero',self.path)
    def test_reject_duplicate_joiner(self):
        add_joiner('B000001','attacker','Charles',self.path)
        with self.assertRaises(ValueError): add_joiner('B000001','attacker','Charles',self.path)
    def test_missing_battle(self):
        with self.assertRaises(KeyError): add_joiner('B999999','attacker','Charles',self.path)
    def test_database_enforces_role_value_contract(self):
        with closing(db.connect(self.path)) as c:
            bid=1
            charles=c.execute("SELECT hero_id FROM heroes WHERE name='Charles'").fetchone()[0]
            with self.assertRaises(sqlite3.IntegrityError):
                c.execute("INSERT INTO battle_heroes(battle_id,side,role,slot,hero_id,join_value) VALUES (?,?,?,?,?,?)",(bid,'defender','joiner',1,charles,8))
        with closing(db.connect(self.path)) as c:
            charles=c.execute("SELECT hero_id FROM heroes WHERE name='Charles'").fetchone()[0]
            with self.assertRaises(sqlite3.IntegrityError):
                c.execute("INSERT INTO battle_heroes(battle_id,side,role,slot,hero_id,join_value) VALUES (?,?,?,?,?,NULL)",(1,'defender','lead',1,charles))
