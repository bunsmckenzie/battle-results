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


if __name__ == '__main__':
    unittest.main()
