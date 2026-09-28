import unittest
from pathlib import Path
from battle_metadata import extract_battle_metadata

FIX = Path(__file__).parent / 'fixtures'


class BattleMetadataTests(unittest.TestCase):
    def test_cropped_outcome_reads_player_names_without_alliance(self):
        m = extract_battle_metadata(FIX / 'outcome.jpg')
        self.assertEqual(m.attacker_name, 'Meridian')
        self.assertEqual(m.defender_name, 'Al KaabiUAE')
        self.assertEqual(m.result, 'DEFEAT')
        self.assertNotIn('[TPG]', m.attacker_name)
        self.assertNotIn('[PGK]', m.defender_name)

    def test_full_outcome_reads_same_metadata(self):
        m = extract_battle_metadata(FIX / 'full_outcome.jpg')
        self.assertEqual((m.attacker_name, m.defender_name, m.result),
                         ('Meridian', 'Al KaabiUAE', 'DEFEAT'))

    def test_full_victory_outcome_reads_victory(self):
        m = extract_battle_metadata(FIX / 'full_outcome_victory.jpg')
        self.assertEqual(m.attacker_name, 'Meridian')
        self.assertEqual(m.defender_name, 'Al KaabiUAE')
        self.assertEqual(m.result, 'VICTORY')

    def test_result_template_rejects_unknown_banner(self):
        import cv2
        import numpy as np
        from battle_metadata import _read_result
        outcome = cv2.imread(str(FIX / 'outcome.jpg'))
        self.assertIsNotNone(outcome)
        outcome = outcome.copy()
        outcome[135:245, 350:660] = np.full((110,310,3), 127, dtype=np.uint8)
        with self.assertRaisesRegex(ValueError, 'Unrecognized battle result'):
            _read_result(outcome)


if __name__ == '__main__':
    unittest.main()
