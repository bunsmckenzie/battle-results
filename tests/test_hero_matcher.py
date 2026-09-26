import unittest
from pathlib import Path

from hero_matcher import HeroMatcher, match_battle_heroes

ROOT = Path(__file__).resolve().parents[1]
FIXTURE = ROOT / "tests" / "fixtures" / "herocomparison.jpg"

class HeroMatcherTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.results = match_battle_heroes(FIXTURE, HeroMatcher())

    def test_all_six_slots_are_returned(self):
        self.assertEqual(len(self.results), 6)

    def test_yang_is_strongly_matched(self):
        match = self.results["attacker.hero3"]
        self.assertTrue(match.accepted)
        self.assertEqual(match.name, "Yang")
        self.assertGreaterEqual(match.good_matches, 10)

    def test_sophia_is_strongly_matched(self):
        match = self.results["defender.hero2"]
        self.assertTrue(match.accepted)
        self.assertEqual(match.name, "Sophia")
        self.assertGreaterEqual(match.good_matches, 10)

    def test_alternate_artwork_is_not_forced_to_a_name(self):
        for slot in ("attacker.hero1", "attacker.hero2", "defender.hero1", "defender.hero3"):
            self.assertFalse(self.results[slot].accepted, slot)
            self.assertIsNone(self.results[slot].name)

    def test_ranked_candidates_are_available_for_review(self):
        match = self.results["attacker.hero1"]
        self.assertEqual(len(match.candidates), 3)
        self.assertGreaterEqual(match.candidates[0].good_matches, match.candidates[1].good_matches)

if __name__ == "__main__":
    unittest.main()
