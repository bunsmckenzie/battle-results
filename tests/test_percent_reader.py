import unittest
from pathlib import Path
import numpy as np, cv2, tempfile
from percent_reader import extract_ratios_bonuses, BONUS_LABELS
ROOT=Path(__file__).resolve().parents[1]
class PercentReaderTests(unittest.TestCase):
 def test_fixture_ratios_and_types(self):
  r=extract_ratios_bonuses(ROOT/'tests/fixtures/ratiosbonuses.jpg')['ratios']
  self.assertEqual([(x['troop_type'],x['reading'].value) for x in r.values()],[('cavalry',49.0),('infantry',48.93),('archer',2.06),('infantry',61.19),('cavalry',38.8)])
 def test_fixture_has_24_bonuses(self):
  b=extract_ratios_bonuses(ROOT/'tests/fixtures/ratiosbonuses.jpg')['bonuses']; self.assertEqual(len(b),24); self.assertEqual(b['attacker.infantry_attack'].value,2109.0); self.assertEqual(b['defender.archer_health'].value,2690.7)
 def test_unknown_image_is_rejected(self):
  with tempfile.TemporaryDirectory() as d:
   p=Path(d)/'x.jpg'; cv2.imwrite(str(p),np.full((2340,1080,3),255,np.uint8))
   with self.assertRaises(ValueError): extract_ratios_bonuses(p)
if __name__=='__main__': unittest.main()
