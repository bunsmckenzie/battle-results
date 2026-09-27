"""Extract stable battle identity metadata from a full Kingshot Outcome screenshot."""
from __future__ import annotations
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
import cv2
import numpy as np
from layout import load_image
from outcome_reader import _norm
from screenshot_preprocessor import is_full_report, normalize_full_report


@dataclass(frozen=True)
class BattleIdentity:
    battle_timestamp: str
    coord_x: int
    coord_y: int

    @property
    def key(self) -> str:
        return f'{self.battle_timestamp.replace(" ", "T")}@{self.coord_x},{self.coord_y}'


class HeaderDigitRecognizer:
    """Read white header digits using the validated outcome digit templates."""
    def __init__(self, template_path: Path | str | None = None):
        template_path = Path(template_path or Path(__file__).resolve().parent / 'assets' / 'outcome_digits.npz')
        data = np.load(template_path)
        self.images = data['images'].astype(np.float32) / 255.0
        self.labels = data['labels'].astype(int)

    def glyphs(self, crop: np.ndarray):
        hsv = cv2.cvtColor(crop, cv2.COLOR_BGR2HSV)
        # Header text is white with a dark outline. Restrict to bright, low-saturation fill.
        mask = cv2.inRange(hsv, (0, 0, 180), (180, 105, 255))
        n, _, stats, _ = cv2.connectedComponentsWithStats(mask, 8)
        templates = self.images.reshape(len(self.images), -1)
        found = []
        for i in range(1, n):
            x, y, w, h, area = map(int, stats[i])
            if not (10 <= w <= 30 and 20 <= h <= 36 and area >= 140):
                continue
            patch = _norm(mask[y:y+h, x:x+w]).astype(np.float32).reshape(1, -1) / 255.0
            distances = np.mean(np.abs(templates - patch), axis=1)
            j = int(np.argmin(distances))
            mismatch = float(distances[j])
            # X/Y letters are tall components too, but mismatch the digit templates strongly.
            if mismatch <= 0.16:
                found.append((x, int(self.labels[j]), 1.0 - mismatch / 0.16))
        return sorted(found, key=lambda item: item[0])

    def read_digits(self, crop: np.ndarray, expected_count: int | None = None) -> tuple[str, float]:
        glyphs = self.glyphs(crop)
        if expected_count is not None and len(glyphs) != expected_count:
            raise ValueError(f'Expected {expected_count} header digits, found {len(glyphs)}')
        if not glyphs:
            raise ValueError('No header digits found')
        return ''.join(str(g[1]) for g in glyphs), min(g[2] for g in glyphs)


def _read_coordinates(image: np.ndarray, recognizer: HeaderDigitRecognizer) -> tuple[int, int]:
    # Wide ROI includes "X:<digits> Y:<digits>". X/Y are rejected by template mismatch.
    crop = image[292:342, 45:360]
    glyphs = recognizer.glyphs(crop)
    if len(glyphs) < 2:
        raise ValueError('Could not read battle coordinates')
    # Split at the largest horizontal gap between digit groups.
    gaps = [(glyphs[i+1][0] - glyphs[i][0], i) for i in range(len(glyphs)-1)]
    gap, split = max(gaps)
    if gap < 35:
        raise ValueError('Could not separate X and Y coordinate groups')
    left, right = glyphs[:split+1], glyphs[split+1:]
    if not left or not right:
        raise ValueError('Incomplete battle coordinates')
    return int(''.join(str(g[1]) for g in left)), int(''.join(str(g[1]) for g in right))


def extract_battle_identity(image_path: Path | str, recognizer: HeaderDigitRecognizer | None = None) -> BattleIdentity | None:
    """Return normalized timestamp/X/Y identity, or None for legacy cropped Outcome images."""
    image = load_image(image_path)
    if not is_full_report(image):
        return None
    image = normalize_full_report(image)
    recognizer = recognizer or HeaderDigitRecognizer()
    coord_x, coord_y = _read_coordinates(image, recognizer)
    digits, _ = recognizer.read_digits(image[292:342, 590:1045], expected_count=14)
    try:
        dt = datetime.strptime(digits, '%Y%m%d%H%M%S')
    except ValueError as exc:
        raise ValueError(f'Invalid battle timestamp digits: {digits}') from exc
    return BattleIdentity(dt.strftime('%Y-%m-%d %H:%M:%S'), coord_x, coord_y)
