import unittest
from pathlib import Path
from battle_identity import extract_battle_identity

FIX=Path(__file__).parent / "fixtures"

class BattleIdentityTests(unittest.TestCase):
    def test_fullscreen_header_extracts_timestamp_and_coordinates(self):
        x=extract_battle_identity(FIX/"full_outcome.jpg")
        self.assertIsNotNone(x)
        self.assertEqual(x.battle_timestamp,"2026-09-26 09:56:21")
        self.assertEqual((x.coord_x,x.coord_y),(597,597))
        self.assertEqual(x.key,"2026-09-26T09:56:21@597,597")

    def test_legacy_cropped_outcome_has_no_identity(self):
        self.assertIsNone(extract_battle_identity(FIX/"outcome.jpg"))

if __name__=="__main__": unittest.main()
