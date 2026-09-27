import shutil, tempfile, unittest
from pathlib import Path
from screenshot_classifier import classify_image, classify_folder
BASE=Path(__file__).parent/'fixtures'
class ScreenshotClassifierTests(unittest.TestCase):
 def test_classifies_all_known_fixtures_without_using_names(self):
  cases=[('outcome.jpg','outcome'),('herocomparison.jpg','heroes'),('ratiosbonuses.jpg','ratios_bonuses'),('ratiosbonuses2.jpg','ratios_bonuses'),('ratiosbonuses3.jpg','ratios_bonuses')]
  with tempfile.TemporaryDirectory() as d:
   for i,(src,expected) in enumerate(cases):
    dst=Path(d)/f'random_{i}.jpg'; shutil.copy2(BASE/src,dst)
    self.assertEqual(classify_image(dst).image_type,expected)
 def test_classifies_fullscreen_user_captures_in_scrambled_order(self):
  cases=[('full_heroes.jpg','heroes'),('full_heroes_shifted.jpg','heroes'),('full_outcome.jpg','outcome'),('full_ratios_counts.jpg','ratios_bonuses')]
  with tempfile.TemporaryDirectory() as d:
   for name,expected in reversed(cases):
    dst=Path(d)/('random_'+str(len(list(Path(d).glob('*.jpg'))))+'.jpg'); shutil.copy2(BASE/name,dst)
    self.assertEqual(classify_image(dst).image_type,expected)

 def test_folder_ignores_nonimages(self):
  with tempfile.TemporaryDirectory() as d:
   shutil.copy2(BASE/'outcome.jpg',Path(d)/'x.jpg'); (Path(d)/'notes.txt').write_text('x')
   r=classify_folder(d); self.assertEqual(len(r),1); self.assertEqual(next(iter(r.values())).image_type,'outcome')
if __name__=='__main__': unittest.main()
