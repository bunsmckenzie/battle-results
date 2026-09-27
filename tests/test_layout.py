import tempfile
import unittest
from pathlib import Path

import cv2
import numpy as np

from layout import LayoutCatalog, NormalizedBox, load_image, write_debug_crops


FIXTURES = Path(__file__).resolve().parent / "fixtures"


class LayoutTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.catalog = LayoutCatalog.load()

    def test_catalog_contains_three_fixture_layouts(self):
        self.assertEqual(
            set(self.catalog.names()),
            {"outcome", "hero_comparison", "ratios_bonuses"},
        )

    def test_all_regions_are_nonempty_and_inside_fixture_images(self):
        cases = {
            "outcome": "outcome.jpg",
            "hero_comparison": "herocomparison.jpg",
            "ratios_bonuses": "ratiosbonuses.jpg",
        }
        for layout_name, filename in cases.items():
            image = load_image(FIXTURES / filename)
            height, width = image.shape[:2]
            for name, box in self.catalog.regions(layout_name).items():
                with self.subTest(layout=layout_name, region=name):
                    x1, y1, x2, y2 = box.pixels(width, height)
                    self.assertGreater(x2, x1)
                    self.assertGreater(y2, y1)
                    self.assertGreater(self.catalog.crop(image, layout_name, name).size, 0)

    def test_normalized_box_scales_with_resolution(self):
        box = NormalizedBox(0.10, 0.20, 0.40, 0.60)
        self.assertEqual(box.pixels(1000, 500), (100, 100, 400, 300))
        self.assertEqual(box.pixels(2000, 1000), (200, 200, 800, 600))

    def test_same_region_keeps_proportional_shape_after_resize(self):
        image = load_image(FIXTURES / "outcome.jpg")
        crop1 = self.catalog.crop(image, "outcome", "attacker.squad")
        resized = cv2.resize(image, None, fx=2.0, fy=2.0, interpolation=cv2.INTER_NEAREST)
        crop2 = self.catalog.crop(resized, "outcome", "attacker.squad")
        self.assertLessEqual(abs(crop2.shape[0] - crop1.shape[0] * 2), 1)
        self.assertLessEqual(abs(crop2.shape[1] - crop1.shape[1] * 2), 1)

    def test_invalid_normalized_boxes_are_rejected(self):
        with self.assertRaises(ValueError):
            NormalizedBox(-0.1, 0.0, 0.5, 0.5)
        with self.assertRaises(ValueError):
            NormalizedBox(0.5, 0.0, 0.5, 0.5)

    def test_debug_crop_writer_creates_one_file_per_region(self):
        with tempfile.TemporaryDirectory() as tempdir:
            written = write_debug_crops(
                FIXTURES / "herocomparison.jpg",
                "hero_comparison",
                tempdir,
                self.catalog,
            )
            self.assertEqual(len(written), 12)
            self.assertTrue(all(path.is_file() for path in written))


if __name__ == "__main__":
    unittest.main()
