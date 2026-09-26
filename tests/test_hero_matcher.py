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

    def test_all_six_fixture_heroes_are_strongly_matched(self):
        expected = {
            "attacker.hero1": "Charles",
            "attacker.hero2": "Ava",
            "attacker.hero3": "Yang",
            "defender.hero1": "Charles",
            "defender.hero2": "Sophia",
            "defender.hero3": "Wee & Woo",
        }
        for slot, name in expected.items():
            match = self.results[slot]
            self.assertTrue(match.accepted, slot)
            self.assertEqual(match.name, name)
            self.assertGreaterEqual(match.good_matches, 10)

    def test_lookup_contains_22_detected_references(self):
        matcher = HeroMatcher()
        self.assertEqual(len(matcher.references), 22)

    def test_ranked_candidates_are_available_for_review(self):
        match = self.results["attacker.hero1"]
        self.assertEqual(len(match.candidates), 3)
        self.assertGreaterEqual(match.candidates[0].good_matches, match.candidates[1].good_matches)

if __name__ == "__main__":
    unittest.main()
