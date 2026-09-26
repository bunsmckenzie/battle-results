"""Numeric OCR helpers with deterministic parsing and explicit confidence."""
from __future__ import annotations

import re
from dataclasses import dataclass
import cv2


@dataclass(frozen=True)
class OCRReading:
    value: int | float
    confidence: float
    text: str


class NumericOCR:
    def __init__(self, engine=None):
        self._engine = engine

    @property
    def ocr(self):
        if self._engine is None:
            try:
                from paddleocr import PaddleOCR
            except ImportError as exc:
                raise RuntimeError(
                    "PaddleOCR is not installed. Run: python -m pip install -r requirements.txt"
                ) from exc
            self._engine = PaddleOCR(
                use_doc_orientation_classify=False,
                use_doc_unwarping=False,
                use_textline_orientation=False,
            )
        return self._engine

    @staticmethod
    def crop(image, box):
        h, w = image.shape[:2]
        x1, y1, x2, y2 = box
        return image[int(y1*h):int(y2*h), int(x1*w):int(x2*w)]

    @staticmethod
    def parse_number(text, allow_decimal=False):
        text = text.replace(' ', '').replace(',', '')
        text = text.replace('O', '0').replace('o', '0')
        pattern = r'[-+]?\d+(?:\.\d+)?' if allow_decimal else r'[-+]?\d+'
        m = re.search(pattern, text)
        if not m:
            raise ValueError(f'No number found in OCR text: {text!r}')
        return float(m.group()) if allow_decimal else int(m.group())

    @staticmethod
    def _extract_text_and_confidence(results):
        texts, scores = [], []
        for result in results:
            data = result.json if hasattr(result, 'json') else None
            if callable(data):
                data = data()
            if isinstance(data, dict):
                inner = data.get('res', data)
                texts.extend(str(x) for x in inner.get('rec_texts', []))
                scores.extend(float(x) for x in inner.get('rec_scores', []))
        if not texts:
            raise ValueError('No OCR text detected')
        confidence = min(scores) if scores else 0.0
        return ' '.join(texts), confidence

    def read_image(self, image, allow_decimal=False) -> OCRReading:
        if image is None or image.size == 0:
            raise ValueError('A non-empty image is required')
        enlarged = cv2.resize(image, None, fx=3, fy=3, interpolation=cv2.INTER_CUBIC)
        results = self.ocr.predict(enlarged)
        text, confidence = self._extract_text_and_confidence(results)
        value = self.parse_number(text, allow_decimal)
        return OCRReading(value, confidence, text)

    def read(self, image, box, allow_decimal=False):
        return self.read_image(self.crop(image, box), allow_decimal).value
