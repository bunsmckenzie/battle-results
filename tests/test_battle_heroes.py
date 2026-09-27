import unittest
from pathlib import Path
from battle_heroes import analyze_battle_heroes

ROOT = Path(__file__).resolve().parents[1]
FIXTURE = ROOT / 'tests' / 'fixtures' / 'herocomparison.jpg'

class BattleHeroesIntegrationTests(unittest.TestCase):
    def test_fixture_combines_names_and_join_values(self):
        readings = analyze_battle_heroes(FIXTURE)
        expected = {
            'attacker.hero1': ('Charles', 10),
            'attacker.hero2': ('Ava', 10),
            'attacker.hero3': ('Yang', 10),
            'defender.hero1': ('Charles', 10),
            'defender.hero2': ('Sophia', 10),
            'defender.hero3': ('Wee & Woo', 10),
        }
        self.assertEqual(set(readings), set(expected))
        for slot, (name, value) in expected.items():
            self.assertEqual(readings[slot].name, name)
            self.assertEqual(readings[slot].join_value, value)

    def test_fullscreen_hero_capture_is_normalized(self):
        r=analyze_battle_heroes(ROOT/'tests/fixtures/full_heroes.jpg')
        self.assertEqual([r[k].name for k in ('attacker.hero1','attacker.hero2','attacker.hero3')],['Charles','Ava','Yang'])
        self.assertEqual([r[k].name for k in ('defender.hero1','defender.hero2','defender.hero3')],['Charles','Sophia','Wee & Woo'])
        self.assertTrue(all(x.join_value==10 for x in r.values()))


    def test_shifted_fullscreen_hero_capture_is_anchored(self):
        r=analyze_battle_heroes(ROOT/'tests/fixtures/full_heroes_shifted.jpg')
        expected={
            'attacker.hero1':('Charles',10),'attacker.hero2':('Ava',10),'attacker.hero3':('Yang',10),
            'defender.hero1':('Charles',10),'defender.hero2':('Sophia',10),'defender.hero3':('Wee & Woo',10),
        }
        self.assertEqual(set(r),set(expected))
        for slot,(name,value) in expected.items():
            self.assertEqual(r[slot].name,name)
            self.assertEqual(r[slot].join_value,value)
            self.assertTrue(r[slot].accepted)


if __name__ == '__main__':
    unittest.main()
