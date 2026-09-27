import unittest
from pathlib import Path
from percent_reader import extract_ratios_bonuses, ratios_from_counts
ROOT=Path(__file__).resolve().parents[1]
EXPECTED={
 'ratiosbonuses.jpg':([48.93,2.06,49.00],[61.19,38.80]),
 'ratiosbonuses2.jpg':([50.23,11.69,38.06],[44.35,5.22,50.42]),
 'ratiosbonuses3.jpg':([49.00,2.00,48.99],[59.50,40.49]),
}
BONUS2_A=[1700.7,1697.3,2456.3,2026.6,1534.6,1531.3,2325.0,1684.6,1680.7,1677.3,2499.6,1822.5]
BONUS3_D=[2438.4,1971.2,2752.4,2744.3,2299.6,1853.9,2622.5,2620.7,2432.6,1964.0,2697.6,2690.7]
class PercentReaderTests(unittest.TestCase):
 def test_all_three_fixture_ratios(self):
  for fn,(a,d) in EXPECTED.items():
   with self.subTest(fn=fn):
    r=extract_ratios_bonuses(ROOT/'tests/fixtures'/fn)['ratios']
    av=[v['reading'].value for k,v in r.items() if k.startswith('attacker.')]
    dv=[v['reading'].value for k,v in r.items() if k.startswith('defender.')]
    self.assertEqual(av,a); self.assertEqual(dv,d)
 def test_ratio_types_follow_ui_order_and_missing_archer_does_not_shift(self):
  r=extract_ratios_bonuses(ROOT/'tests/fixtures/ratiosbonuses.jpg')['ratios']
  self.assertEqual([v['troop_type'] for v in r.values()],['infantry','cavalry','archer','infantry','cavalry'])
 def test_second_fixture_bonuses(self):
  b=extract_ratios_bonuses(ROOT/'tests/fixtures/ratiosbonuses2.jpg')['bonuses']
  self.assertEqual([b[f'attacker.{x}'].value for x in __import__('percent_reader').BONUS_LABELS],BONUS2_A)
 def test_third_fixture_defender_bonuses(self):
  b=extract_ratios_bonuses(ROOT/'tests/fixtures/ratiosbonuses3.jpg')['bonuses']
  self.assertEqual([b[f'defender.{x}'].value for x in __import__('percent_reader').BONUS_LABELS],BONUS3_D)
 def test_each_fixture_has_24_bonuses(self):
  for fn in EXPECTED:
   self.assertEqual(len(extract_ratios_bonuses(ROOT/'tests/fixtures'/fn)['bonuses']),24)

 def test_troop_and_tg_levels_all_fixtures(self):
  expected={
   'ratiosbonuses.jpg':([10.9,10.8,10.9],[7,7,7],[10.7,10.5],[7,7]),
   'ratiosbonuses2.jpg':([10.4,10.3,10.5],[7,7,7],[10.7,10.2,10.7],[7,7,7]),
   'ratiosbonuses3.jpg':([11.0,10.8,11.0],[8,8,8],[10.8,10.7],[7,7]),
  }
  for fn,(al,at,dl,dt) in expected.items():
   with self.subTest(fn=fn):
    r=extract_ratios_bonuses(ROOT/'tests/fixtures'/fn)['ratios']
    a=[v for k,v in r.items() if k.startswith('attacker.')]
    d=[v for k,v in r.items() if k.startswith('defender.')]
    self.assertEqual([v['troop_level'].value for v in a],al); self.assertEqual([v['tg_level'].value for v in a],at)
    self.assertEqual([v['troop_level'].value for v in d],dl); self.assertEqual([v['tg_level'].value for v in d],dt)

 def test_fullscreen_count_view_derives_ratios_and_levels(self):
  r=extract_ratios_bonuses(ROOT/'tests/fixtures/full_ratios_counts.jpg')
  a=[v for k,v in r['ratios'].items() if k.startswith('attacker.')]
  d=[v for k,v in r['ratios'].items() if k.startswith('defender.')]
  self.assertEqual([v['reading'].value for v in a],[49.0,2.0,49.0])
  self.assertEqual([v['reading'].value for v in d],[48.43,1.94,49.63])
  self.assertEqual([v['troop_level'].value for v in a],[11.0,10.8,11.0])
  self.assertEqual([v['tg_level'].value for v in a],[8,8,8])
  self.assertEqual([v['troop_level'].value for v in d],[10.8,10.6,10.5])
  self.assertEqual([v['tg_level'].value for v in d],[7,7,7])
  self.assertEqual(r['bonuses']['defender.infantry_attack'].value,2438.4)


 def test_absolute_counts_are_converted_to_ratios(self):
  self.assertEqual(ratios_from_counts([778528,31779,778525]),[49.0,2.0,49.0])
  self.assertEqual(ratios_from_counts([791233,31655,810944]),[48.43,1.94,49.63])

 def test_percentage_view_is_passed_through(self):
  r=extract_ratios_bonuses(ROOT/'tests/fixtures/ratiosbonuses.jpg')
  self.assertEqual(r['ratio_input_mode'],'ratios')
  a=[v['reading'].value for k,v in r['ratios'].items() if k.startswith('attacker.')]
  self.assertEqual(a,[48.93,2.06,49.0])

 def test_count_view_reports_counts_mode_and_calculated_ratios(self):
  r=extract_ratios_bonuses(ROOT/'tests/fixtures/full_ratios_counts.jpg')
  self.assertEqual(r['ratio_input_mode'],'counts')
  a=[v['reading'].value for k,v in r['ratios'].items() if k.startswith('attacker.')]
  self.assertEqual(a,[49.0,2.0,49.0])


 def test_additional_fullscreen_count_views_with_two_or_three_defender_cards(self):
  expected={
   'new_rb/rb1.jpg':([49.0,2.0,49.0],[48.43,1.94,49.63]),
   'new_rb/rb2.jpg':([49.0,2.0,49.0],[59.51,40.49]),
   'new_rb/rb3.jpg':([49.0,2.0,49.0],[50.2,2.3,47.5]),
   'new_rb/rb4.jpg':([48.93,2.06,49.0],[61.19,38.81]),
  }
  for fn,(ae,de) in expected.items():
   with self.subTest(fn=fn):
    r=extract_ratios_bonuses(ROOT/'tests/fixtures'/fn)
    self.assertEqual(r['ratio_input_mode'],'counts')
    a=[v['reading'].value for k,v in r['ratios'].items() if k.startswith('attacker.')]
    d=[v['reading'].value for k,v in r['ratios'].items() if k.startswith('defender.')]
    self.assertEqual(a,ae); self.assertEqual(d,de)

if __name__=='__main__': unittest.main()
