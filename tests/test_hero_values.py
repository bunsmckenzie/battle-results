import unittest
import numpy as np
from pathlib import Path

from hero_values import extract_battle_join_values, validate_join_value
from ocr import NumericOCR, OCRReading
from join_value_recognizer import ConstrainedJoinValueRecognizer

FIXTURES = Path(__file__).resolve().parent / "fixtures"


class FakeOCR:
    def __init__(self, values):
        self.values = iter(values)

    def read_image(self, image, allow_decimal=False):
        value = next(self.values)
        return OCRReading(value=value, confidence=0.99, text=f"+{value}")


class FakeResult:
    def __init__(self, texts, scores):
        self.json = {"res": {"rec_texts": texts, "rec_scores": scores}}


class HeroValueTests(unittest.TestCase):
    def test_join_value_domain_accepts_zero_through_ten(self):
        for value in range(11):
            self.assertEqual(validate_join_value(value), value)

    def test_join_value_domain_rejects_out_of_range_and_non_integer(self):
        for value in (-1, 11, 3.5, True):
            with self.subTest(value=value), self.assertRaises(ValueError):
                validate_join_value(value)

    def test_numeric_parser_handles_plus_sign_and_common_o_confusion(self):
        self.assertEqual(NumericOCR.parse_number("+10"), 10)
        self.assertEqual(NumericOCR.parse_number("+1O"), 10)
        self.assertEqual(NumericOCR.parse_number("  +9 "), 9)

    def test_paddle_result_adapter_preserves_confidence(self):
        text, confidence = NumericOCR._extract_text_and_confidence(
            [FakeResult(["+10"], [0.97])]
        )
        self.assertEqual(text, "+10")
        self.assertAlmostEqual(confidence, 0.97)

    def test_fixture_has_exactly_six_join_value_regions(self):
        readings = extract_battle_join_values(
            FIXTURES / "herocomparison.jpg", FakeOCR([10, 9, 8, 7, 6, 5])
        )
        self.assertEqual(len(readings), 6)
        self.assertEqual(set(readings), {
            "attacker.hero1", "defender.hero1", "attacker.hero2",
            "defender.hero2", "attacker.hero3", "defender.hero3",
        })
        self.assertEqual(sorted(r.value for r in readings.values()), [5,6,7,8,9,10])

    def test_real_fixture_recognizes_all_six_as_ten_without_paddle(self):
        readings = extract_battle_join_values(FIXTURES / "herocomparison.jpg")
        self.assertEqual(len(readings), 6)
        self.assertTrue(all(r.value == 10 for r in readings.values()))
        self.assertTrue(all(r.raw_text == "+10" for r in readings.values()))
        self.assertTrue(all(r.confidence >= 0.70 for r in readings.values()))

    def test_constrained_recognizer_rejects_unrecognized_image(self):
        blank = np.zeros((88, 103, 3), dtype=np.uint8)
        with self.assertRaisesRegex(ValueError, "UNKNOWN hero join value"):
            ConstrainedJoinValueRecognizer().read_image(blank)

    def test_out_of_range_ocr_is_rejected_not_stored(self):
        with self.assertRaisesRegex(ValueError, "between 0 and 10"):
            extract_battle_join_values(
                FIXTURES / "herocomparison.jpg", FakeOCR([10, 10, 10, 10, 10, 99])
            )


if __name__ == "__main__":
    unittest.main()
