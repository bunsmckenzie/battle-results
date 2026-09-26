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

# Hero names in visual order in the lookup image. Card positions are detected
# from the image itself rather than tied to one lookup image height.
_REFERENCE_NAMES = (
    "Ava", "Charles", "Wee & Woo",
    "Yang", "Triton", "Sophia",
    "Vivian", "Long Fei", "Thrud",
    "Rosa", "Alcar", "Margot",
    "Jaeger", "Eric", "Petra",
    "Hilde", "Zoe", "Marlin",
    "Jabel", "Amadeus", "Helga", "Saul",
)

def _detect_reference_boxes(lookup: np.ndarray) -> list[tuple[int, int, int, int]]:
    """Detect the portrait grid and return boxes in visual reading order.

    Canny edges locate the repeated portrait frames. Their Y positions establish
    generation rows; portrait columns are proportional to image width. This also
    recovers a card when one portrait's artwork does not yield a clean contour.
    """
    gray = cv2.cvtColor(lookup, cv2.COLOR_BGR2GRAY)
    edges = cv2.Canny(gray, 80, 160)
    contours, _ = cv2.findContours(edges, cv2.RETR_LIST, cv2.CHAIN_APPROX_SIMPLE)
    h, w = lookup.shape[:2]
    candidates = []
    for contour in contours:
        x, y, bw, bh = cv2.boundingRect(contour)
        if 0.18 * w <= bw <= 0.22 * w and 0.045 * h <= bh <= 0.060 * h:
            candidates.append((x, y, bw, bh))
    if not candidates:
        raise ValueError("Could not detect hero portrait rows in lookup image")

    ys = sorted(y for _, y, _, _ in candidates)
    rows: list[list[int]] = []
    row_gap = max(50, round(0.016 * h))
    for y in ys:
        if not rows or y - rows[-1][-1] > row_gap:
            rows.append([y])
        else:
            rows[-1].append(y)
    if len(rows) != 7:
        raise ValueError(f"Expected 7 hero generations in lookup image; detected {len(rows)}")

    row_tops = [round(sum(row) / len(row)) for row in rows]
    centers = (0.135, 0.385, 0.635)
    portrait_w, portrait_h = round(0.177 * w), round(0.044 * h)
    y_inset = round(0.0032 * h)
    boxes = []
    for row_index, y in enumerate(row_tops):
        row_centers = centers + ((0.885,) if row_index == len(row_tops) - 1 else ())
        for center in row_centers:
            x1 = round(center * w - portrait_w / 2)
            y1 = y + y_inset
            boxes.append((x1, y1, x1 + portrait_w, y1 + portrait_h))
    if len(boxes) != len(_REFERENCE_NAMES):
        raise ValueError(f"Detected {len(boxes)} reference portraits but catalog has {len(_REFERENCE_NAMES)} heroes")
    return boxes

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
        refs = {}
        boxes = _detect_reference_boxes(lookup)
        for name, (x1, y1, x2, y2) in zip(_REFERENCE_NAMES, boxes):
            crop = lookup[y1:y2, x1:x2]
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
