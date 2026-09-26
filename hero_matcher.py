"""Conservative hero portrait matching against the reference lookup image.

The battle UI can use alternate hero artwork/skins.  This matcher therefore
only accepts a result when local SIFT features provide strong evidence; it
never turns a weak nearest-neighbour result into a hero name.
"""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import cv2
import numpy as np

from layout import BASE_DIR, LayoutCatalog, load_image

DEFAULT_LOOKUP = BASE_DIR / "assets" / "heroes" / "hero_lookup.png"

# Pixel boxes for the portrait artwork in the current 1300x3350 lookup asset.
# They are converted to normalized coordinates at load time, so a proportionally
# resized copy of the lookup image remains usable.
_REFERENCE_SIZE = (1300, 3350)
_REFERENCE_BOXES = {
    "Yang": (52, 127, 286, 337), "Triton": (376, 127, 609, 337), "Sophia": (700, 127, 934, 337),
    "Vivian": (52, 693, 286, 900), "Long Fei": (376, 693, 609, 900), "Thrud": (700, 693, 934, 900),
    "Rosa": (52, 1229, 286, 1441), "Alcar": (376, 1229, 609, 1441), "Margot": (700, 1229, 934, 1441),
    "Jaeger": (52, 1800, 286, 2009), "Eric": (376, 1800, 609, 2009), "Petra": (700, 1800, 934, 2009),
    "Hilde": (35, 2365, 269, 2570), "Zoe": (357, 2365, 590, 2570), "Marlin": (680, 2365, 914, 2570),
    "Jabel": (35, 2915, 269, 3125), "Amadeus": (357, 2915, 590, 3125), "Helga": (680, 2915, 914, 3125),
    "Saul": (1005, 2915, 1238, 3125),
}

@dataclass(frozen=True)
class Candidate:
    name: str
    good_matches: int

@dataclass(frozen=True)
class HeroMatch:
    name: str | None
    confidence: float
    good_matches: int
    runner_up_matches: int
    candidates: tuple[Candidate, ...]

    @property
    def accepted(self) -> bool:
        return self.name is not None

class HeroMatcher:
    def __init__(self, lookup_path: Path | str = DEFAULT_LOOKUP, *, min_good_matches: int = 10, min_margin: int = 5):
        self.lookup_path = Path(lookup_path)
        self.min_good_matches = min_good_matches
        self.min_margin = min_margin
        self.sift = cv2.SIFT_create()
        self.matcher = cv2.BFMatcher(cv2.NORM_L2)
        lookup = load_image(self.lookup_path)
        self.references = self._build_references(lookup)

    def _build_references(self, lookup: np.ndarray):
        h, w = lookup.shape[:2]
        rw, rh = _REFERENCE_SIZE
        refs = {}
        for name, (x1, y1, x2, y2) in _REFERENCE_BOXES.items():
            px1, px2 = round(x1 / rw * w), round(x2 / rw * w)
            py1, py2 = round(y1 / rh * h), round(y2 / rh * h)
            crop = lookup[py1:py2, px1:px2]
            gray = cv2.cvtColor(crop, cv2.COLOR_BGR2GRAY)
            _, descriptors = self.sift.detectAndCompute(gray, None)
            refs[name] = descriptors
        return refs

    def _score(self, query_descriptors, reference_descriptors) -> int:
        if query_descriptors is None or reference_descriptors is None or len(reference_descriptors) < 2:
            return 0
        pairs = self.matcher.knnMatch(query_descriptors, reference_descriptors, k=2)
        return sum(1 for first, second in pairs if first.distance < 0.70 * second.distance)

    def match(self, portrait: np.ndarray) -> HeroMatch:
        if portrait is None or portrait.size == 0:
            raise ValueError("A non-empty portrait image is required")
        gray = cv2.cvtColor(portrait, cv2.COLOR_BGR2GRAY)
        _, query = self.sift.detectAndCompute(gray, None)
        ranked = sorted(
            (Candidate(name, self._score(query, descriptors)) for name, descriptors in self.references.items()),
            key=lambda item: (-item.good_matches, item.name),
        )
        best, runner = ranked[0], ranked[1]
        margin = best.good_matches - runner.good_matches
        accepted = best.good_matches >= self.min_good_matches and margin >= self.min_margin
        # Confidence is evidence-oriented, not a statistical probability.
        strength = min(1.0, best.good_matches / 20.0)
        separation = min(1.0, max(0, margin) / 10.0)
        confidence = round(0.65 * strength + 0.35 * separation, 3)
        return HeroMatch(best.name if accepted else None, confidence, best.good_matches, runner.good_matches, tuple(ranked[:3]))


def match_battle_heroes(image_path: Path | str, matcher: HeroMatcher | None = None) -> dict[str, HeroMatch]:
    image = load_image(image_path)
    catalog = LayoutCatalog.load()
    matcher = matcher or HeroMatcher()
    result = {}
    for region_name in catalog.regions("hero_comparison"):
        if not region_name.endswith(".portrait"):
            continue
        portrait = catalog.crop(image, "hero_comparison", region_name)
        result[region_name.removesuffix(".portrait")] = matcher.match(portrait)
    return result
