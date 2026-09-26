"""Resolution-independent screenshot layout/cropping utilities.

Step 2 intentionally contains no OCR.  It translates normalized [0,1]
coordinates into pixel rectangles and returns deterministic crops.
"""
from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Mapping

import cv2
import numpy as np

BASE_DIR = Path(__file__).resolve().parent
DEFAULT_LAYOUT_PATH = BASE_DIR / "config" / "layout.json"


@dataclass(frozen=True)
class NormalizedBox:
    x1: float
    y1: float
    x2: float
    y2: float

    def __post_init__(self):
        values = (self.x1, self.y1, self.x2, self.y2)
        if not all(0.0 <= value <= 1.0 for value in values):
            raise ValueError(f"Normalized coordinates must be within [0, 1]: {values}")
        if self.x1 >= self.x2 or self.y1 >= self.y2:
            raise ValueError(f"Invalid box ordering: {values}")

    def pixels(self, width: int, height: int) -> tuple[int, int, int, int]:
        if width <= 0 or height <= 0:
            raise ValueError("Image width and height must be positive")
        x1 = max(0, min(width - 1, round(self.x1 * width)))
        y1 = max(0, min(height - 1, round(self.y1 * height)))
        x2 = max(x1 + 1, min(width, round(self.x2 * width)))
        y2 = max(y1 + 1, min(height, round(self.y2 * height)))
        return x1, y1, x2, y2


class LayoutCatalog:
    def __init__(self, layouts: Mapping[str, Mapping[str, NormalizedBox]], version: int):
        self.layouts = dict(layouts)
        self.version = version

    @classmethod
    def load(cls, path: Path | str = DEFAULT_LAYOUT_PATH) -> "LayoutCatalog":
        path = Path(path)
        raw = json.loads(path.read_text(encoding="utf-8"))
        parsed = {}
        for layout_name, spec in raw["layouts"].items():
            parsed[layout_name] = {
                name: NormalizedBox(*coords)
                for name, coords in spec["regions"].items()
            }
        return cls(parsed, raw["version"])

    def names(self) -> tuple[str, ...]:
        return tuple(self.layouts)

    def regions(self, layout_name: str) -> Mapping[str, NormalizedBox]:
        try:
            return self.layouts[layout_name]
        except KeyError as exc:
            raise KeyError(
                f"Unknown layout {layout_name!r}; expected one of {', '.join(self.names())}"
            ) from exc

    def crop(self, image: np.ndarray, layout_name: str, region_name: str) -> np.ndarray:
        if image is None or image.ndim < 2:
            raise ValueError("A valid image array is required")
        try:
            box = self.regions(layout_name)[region_name]
        except KeyError as exc:
            raise KeyError(f"Unknown region {region_name!r} for layout {layout_name!r}") from exc
        height, width = image.shape[:2]
        x1, y1, x2, y2 = box.pixels(width, height)
        return image[y1:y2, x1:x2].copy()

    def crop_all(self, image: np.ndarray, layout_name: str) -> dict[str, np.ndarray]:
        return {
            name: self.crop(image, layout_name, name)
            for name in self.regions(layout_name)
        }


def load_image(path: Path | str) -> np.ndarray:
    path = Path(path)
    image = cv2.imread(str(path))
    if image is None:
        raise ValueError(f"Could not read image: {path}")
    return image


def write_debug_crops(
    image_path: Path | str,
    layout_name: str,
    output_dir: Path | str,
    catalog: LayoutCatalog | None = None,
) -> list[Path]:
    """Write one image per configured region for visual geometry inspection."""
    catalog = catalog or LayoutCatalog.load()
    image = load_image(image_path)
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    written = []
    for name, crop in catalog.crop_all(image, layout_name).items():
        safe_name = name.replace(".", "__")
        destination = output_dir / f"{safe_name}.png"
        if not cv2.imwrite(str(destination), crop):
            raise OSError(f"Could not write debug crop: {destination}")
        written.append(destination)
    return written
