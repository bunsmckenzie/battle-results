"""Conservative recognizer for the tiny hero join-value badge.

The current real fixture only contains +10.  We positively recognize +10 from
its glyph geometry (a narrow '1' immediately followed by a hole-bearing '0').
Single-digit values are deliberately rejected until real labeled examples are
available; guessing would silently corrupt battle data.
"""
from __future__ import annotations
from dataclasses import dataclass
import cv2
import numpy as np


@dataclass(frozen=True)
class JoinGlyphReading:
    value: int
    confidence: float
    text: str


class ConstrainedJoinValueRecognizer:
    def read_image(self, image, allow_decimal=False) -> JoinGlyphReading:
        if image is None or image.size == 0:
            raise ValueError("A non-empty image is required")
        if allow_decimal:
            raise ValueError("Hero join values are integers only")

        h, w = image.shape[:2]
        hsv = cv2.cvtColor(image, cv2.COLOR_BGR2HSV)
        # Badge text is bright, low-saturation white. Work only in the
        # upper-right text zone so the equipment artwork is mostly excluded.
        mask = cv2.inRange(hsv, (0, 0, 180), (179, 95, 255))
        x0, x1 = int(0.35 * w), int(0.85 * w)
        y0, y1 = int(0.08 * h), int(0.56 * h)
        roi = mask[y0:y1, x0:x1]

        contours, hierarchy = cv2.findContours(
            roi, cv2.RETR_CCOMP, cv2.CHAIN_APPROX_SIMPLE
        )
        if hierarchy is None:
            raise ValueError("UNKNOWN hero join value: no text glyphs detected")

        glyphs = []
        for i, contour in enumerate(contours):
            # Only outer contours; child contours represent holes.
            if hierarchy[0][i][3] != -1:
                continue
            x, y, cw, ch = cv2.boundingRect(contour)
            area = cv2.contourArea(contour)
            if ch < max(10, int(0.14 * h)) or area < 20:
                continue
            has_hole = hierarchy[0][i][2] != -1
            glyphs.append((x, y, cw, ch, area, has_hole))

        # In this font the zero is a compact hole-bearing glyph at the right.
        zeros = [g for g in glyphs if g[5] and 0.50 <= g[2] / g[3] <= 1.05]
        for zero in sorted(zeros, key=lambda g: g[0], reverse=True):
            zx, zy, zw, zh, _, _ = zero
            ones = [
                g for g in glyphs
                if not g[5]
                and g[0] < zx
                and 0 <= zx - (g[0] + g[2]) <= max(5, int(0.08 * w))
                and 0.18 <= g[2] / g[3] <= 0.60
                and 0.70 <= g[3] / zh <= 1.30
            ]
            if ones:
                one = max(ones, key=lambda g: g[0])
                gap = zx - (one[0] + one[2])
                # Geometry is intentionally interpretable rather than a fake
                # neural confidence.  Current fixture scores near 1.0.
                zero_shape = 1.0 - min(abs((zw / zh) - 0.75) / 0.50, 1.0)
                height_match = 1.0 - min(abs(one[3] - zh) / max(zh, 1), 1.0)
                gap_score = 1.0 - min(gap / max(5.0, 0.08 * w), 1.0)
                confidence = float(np.clip((zero_shape + height_match + gap_score) / 3, 0, 1))
                return JoinGlyphReading(10, confidence, "+10")

        raise ValueError(
            "UNKNOWN hero join value: this glyph pattern is not yet validated. "
            "Add a labeled real screenshot for values 0-9 rather than guessing."
        )
