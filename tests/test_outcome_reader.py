import unittest
from pathlib import Path
import cv2
import numpy as np
from outcome_reader import OutcomeDigitRecognizer, extract_battle_outcome

ROOT=Path(__file__).resolve().parents[1]

class OutcomeReaderTests(unittest.TestCase):
    def test_fixture_reads_all_twelve_values(self):
        got=extract_battle_outcome(ROOT/'tests'/'fixtures'/'outcome.jpg')
        expected={
          'attacker.power':-75044045,'attacker.squad':1588832,'attacker.losses':0,
          'attacker.injured':556102,'attacker.lightly_injured':1032730,'attacker.residents':0,
          'defender.power':-34876020,'defender.squad':1633832,'defender.losses':0,
          'defender.injured':262089,'defender.lightly_injured':486720,'defender.residents':885023,
        }
        self.assertEqual({k:v.value for k,v in got.items()},expected)
        self.assertTrue(all(0 <= v.confidence <= 1 for v in got.values()))

    def test_blank_crop_is_rejected(self):
        r=OutcomeDigitRecognizer(ROOT/'assets'/'outcome_digits.npz')
        with self.assertRaises(ValueError): r.read(np.full((57,220,3),255,np.uint8))

    def test_fullscreen_capture_is_normalized_and_read_correctly(self):
        r=extract_battle_outcome(ROOT/'tests/fixtures/full_outcome.jpg')
        expected={
            'attacker.power':-75044180,'attacker.squad':1588832,'attacker.losses':0,
            'attacker.injured':556103,'attacker.lightly_injured':1032729,'attacker.residents':0,
            'defender.power':-31304981,'defender.squad':1633832,'defender.losses':0,
            'defender.injured':239587,'defender.lightly_injured':444921,'defender.residents':949324,
        }
        self.assertEqual({k:v.value for k,v in r.items()},expected)

if __name__=='__main__': unittest.main()
