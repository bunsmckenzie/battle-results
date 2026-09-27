import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
from screenshot_classifier import Classification
from folder_router import resolve_battle_images


class FolderRouterTests(unittest.TestCase):
    def _folder(self, names):
        td = tempfile.TemporaryDirectory()
        root = Path(td.name)
        for name in names:
            (root / name).write_bytes(b'x')
        return td, root

    def test_resolves_arbitrary_filenames(self):
        td, root = self._folder(['random_alpha.jpg','random_beta.jpg','random_gamma.jpg'])
        results = {
            str(root/'random_alpha.jpg'): Classification('heroes', .84),
            str(root/'random_beta.jpg'): Classification('outcome', .57),
            str(root/'random_gamma.jpg'): Classification('ratios_bonuses', 1.0),
        }
        try:
            with patch('folder_router.classify_folder', return_value=results):
                r = resolve_battle_images(root)
            self.assertEqual(Path(r['outcome']).name, 'random_beta.jpg')
            self.assertEqual(Path(r['heroes']).name, 'random_alpha.jpg')
            self.assertEqual(Path(r['ratios_bonuses']).name, 'random_gamma.jpg')
        finally: td.cleanup()

    def test_rejects_missing_domain(self):
        td, root = self._folder(['a.jpg','b.jpg'])
        results = {str(root/'a.jpg'): Classification('outcome', .8), str(root/'b.jpg'): Classification('heroes', .8)}
        try:
            with patch('folder_router.classify_folder', return_value=results):
                with self.assertRaisesRegex(ValueError, 'missing ratios_bonuses image'):
                    resolve_battle_images(root)
        finally: td.cleanup()

    def test_rejects_duplicate_domain(self):
        td, root = self._folder(['a.jpg','b.jpg','c.jpg','d.jpg'])
        results = {
            str(root/'a.jpg'): Classification('outcome', .8), str(root/'b.jpg'): Classification('outcome', .9),
            str(root/'c.jpg'): Classification('heroes', .8), str(root/'d.jpg'): Classification('ratios_bonuses', .9),
        }
        try:
            with patch('folder_router.classify_folder', return_value=results):
                with self.assertRaisesRegex(ValueError, 'multiple outcome images'):
                    resolve_battle_images(root)
        finally: td.cleanup()

    def test_unknown_does_not_fill_missing_domain(self):
        td, root = self._folder(['a.jpg','b.jpg','c.jpg'])
        results = {
            str(root/'a.jpg'): Classification('outcome', .8), str(root/'b.jpg'): Classification('heroes', .8),
            str(root/'c.jpg'): Classification('unknown', .4),
        }
        try:
            with patch('folder_router.classify_folder', return_value=results):
                with self.assertRaisesRegex(ValueError, 'missing ratios_bonuses image'):
                    resolve_battle_images(root)
        finally: td.cleanup()

if __name__ == '__main__': unittest.main()
