"""Extract the single top-most adjacent equipment value for each battle hero."""
from __future__ import annotations
from dataclasses import dataclass
from pathlib import Path

from layout import LayoutCatalog, load_image
from ocr import NumericOCR

MIN_JOIN_VALUE = 0
MAX_JOIN_VALUE = 10


@dataclass(frozen=True)
class JoinValueReading:
    value: int
    confidence: float
    raw_text: str


def validate_join_value(value: int) -> int:
    if isinstance(value, bool) or not isinstance(value, int):
        raise ValueError(f"Hero join value must be an integer, got {value!r}")
    if not MIN_JOIN_VALUE <= value <= MAX_JOIN_VALUE:
        raise ValueError(f"Hero join value must be between 0 and 10, got {value}")
    return value


def extract_battle_join_values(image_path: Path | str, ocr: NumericOCR | None = None) -> dict[str, JoinValueReading]:
    image = load_image(image_path)
    catalog = LayoutCatalog.load()
    ocr = ocr or NumericOCR()
    readings = {}
    for region_name in catalog.regions("hero_comparison"):
        if not region_name.endswith(".join_value"):
            continue
        crop = catalog.crop(image, "hero_comparison", region_name)
        reading = ocr.read_image(crop)
        value = validate_join_value(reading.value)
        readings[region_name.removesuffix(".join_value")] = JoinValueReading(
            value=value, confidence=reading.confidence, raw_text=reading.text
        )
    if len(readings) != 6:
        raise ValueError(f"Expected 6 hero join values; extracted {len(readings)}")
    return readings
