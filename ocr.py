import re
import cv2
from paddleocr import PaddleOCR


class NumericOCR:
    def __init__(self):
        self.ocr = PaddleOCR(
            use_doc_orientation_classify=False,
            use_doc_unwarping=False,
            use_textline_orientation=False,
        )

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

    def read(self, image, box, allow_decimal=False):
        crop = self.crop(image, box)
        crop = cv2.resize(crop, None, fx=3, fy=3, interpolation=cv2.INTER_CUBIC)
        results = self.ocr.predict(crop)
        texts = []
        for result in results:
            # PaddleOCR 3.x exposes a JSON-like result representation.
            data = result.json if hasattr(result, 'json') else None
            if callable(data):
                data = data()
            if isinstance(data, dict):
                inner = data.get('res', data)
                texts.extend(inner.get('rec_texts', []))
        if not texts:
            raise ValueError('No OCR text detected')
        return self.parse_number(' '.join(texts), allow_decimal)
