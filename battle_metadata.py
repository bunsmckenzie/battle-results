"""Read human battle metadata from the Battle Overview panel.

Player names are OCR'd only after the alliance tag has been removed structurally
from the image.  The report result is normalized to VICTORY or DEFEAT.

Tesseract is used only for free-form player text.  The rest of the battle pipeline
remains deterministic OpenCV recognition.  On Windows we also probe the common
UB-Mannheim installation locations when tesseract.exe is not on PATH.
"""
from __future__ import annotations
from dataclasses import dataclass
from pathlib import Path
import os
import re
import shutil
import subprocess
import tempfile

import cv2
import numpy as np

from layout import load_image
from screenshot_preprocessor import prepare_outcome


@dataclass(frozen=True)
class BattleMetadata:
    attacker_name: str
    defender_name: str
    result: str


# Coordinates in the canonical 1001x955 Battle Overview crop.
_NAME_BOXES = {
    'attacker': (70, 285, 390, 360),
    'defender': (590, 285, 970, 360),
}
_RESULT_BOX = (350, 135, 660, 245)


def _find_tesseract() -> str:
    found = shutil.which('tesseract')
    if found:
        return found
    if os.name == 'nt':
        candidates = [
            Path(os.environ.get('ProgramFiles', r'C:\Program Files')) / 'Tesseract-OCR' / 'tesseract.exe',
            Path(os.environ.get('ProgramFiles(x86)', r'C:\Program Files (x86)')) / 'Tesseract-OCR' / 'tesseract.exe',
            Path(os.environ.get('LOCALAPPDATA', '')) / 'Programs' / 'Tesseract-OCR' / 'tesseract.exe',
        ]
        for p in candidates:
            if p.is_file():
                return str(p)
    raise RuntimeError(
        'Player-name OCR requires Tesseract OCR. Install Tesseract and ensure '
        '`tesseract --version` works, then retry.'
    )


def _ocr_binary(binary: np.ndarray, psm: int = 7) -> str:
    exe = _find_tesseract()
    with tempfile.TemporaryDirectory() as td:
        path = Path(td) / 'ocr.png'
        cv2.imwrite(str(path), binary)
        proc = subprocess.run(
            [exe, str(path), 'stdout', '--psm', str(psm), '-l', 'eng'],
            capture_output=True, text=True, encoding='utf-8', errors='replace',
            timeout=20,
        )
    if proc.returncode != 0:
        detail = (proc.stderr or '').strip()
        raise RuntimeError(f'Tesseract OCR failed: {detail or proc.returncode}')
    return ' '.join(proc.stdout.split()).strip()


def _components_for_name(crop: np.ndarray):
    gray = cv2.cvtColor(crop, cv2.COLOR_BGR2GRAY)
    # White name glyph interiors survive this threshold while portraits/background do not.
    bw = cv2.threshold(gray, 210, 255, cv2.THRESH_BINARY)[1]
    n, labels, stats, _ = cv2.connectedComponentsWithStats(bw, 8)
    base = []
    for i in range(1, n):
        x, y, w, h, area = map(int, stats[i])
        if area >= 40 and y >= 15 and y + h >= 50:
            base.append((i, x, y, w, h, area))
    base.sort(key=lambda z: z[1])
    return bw, labels, stats, base


def _player_name_mask(crop: np.ndarray) -> tuple[np.ndarray, np.ndarray | None]:
    """Return baseline-name mask and optional raised-suffix mask.

    The alliance tag is identified by its two tall, narrow bracket components and
    removed geometrically rather than asking OCR to understand the tag.
    """
    bw, labels, stats, base = _components_for_name(crop)
    bracket_candidates = [z for z in base if z[3] <= 8 and z[4] >= 24]
    if len(bracket_candidates) < 2:
        raise ValueError('Could not locate alliance tag brackets in player-name region')
    closing = bracket_candidates[1]
    start_x = closing[1] + closing[3] + 2

    player_base = [z for z in base if z[1] >= start_x]
    if not player_base:
        raise ValueError('No player-name glyphs found after alliance tag')

    keep = {z[0] for z in player_base}
    # Restore dots/accents that belong to baseline glyphs (e.g. i) while excluding
    # raised suffix text unless it sits beyond the baseline name.
    for i in range(1, len(stats)):
        x, y, w, h, area = map(int, stats[i])
        if i in keep or area < 8 or y < 15:
            continue
        cx = x + w / 2
        if any(bx - 2 <= cx <= bx + bwidth + 2 for _, bx, by, bwidth, bh, ba in player_base):
            keep.add(i)

    baseline = np.zeros_like(bw)
    for i in keep:
        baseline[labels == i] = 255

    # Raised suffixes (such as UAE in the validated defender name) sit above the
    # baseline and to the right of the last normal-height glyph. Preserve them as
    # part of the player name, but OCR them separately for much better accuracy.
    last_baseline_right = max(x + w for _, x, y, w, h, a in player_base)
    suffix = np.zeros_like(bw)
    for i in range(1, len(stats)):
        x, y, w, h, area = map(int, stats[i])
        if area >= 40 and y + h < 48 and x >= last_baseline_right - 4:
            suffix[labels == i] = 255

    return _tight_scaled(baseline, 4), (_tight_scaled(suffix, 5) if np.any(suffix) else None)


def _tight_scaled(mask: np.ndarray, scale: int) -> np.ndarray:
    ys, xs = np.where(mask > 0)
    if len(xs) == 0:
        raise ValueError('Empty OCR mask')
    x1, x2 = max(0, xs.min() - 4), min(mask.shape[1], xs.max() + 5)
    y1, y2 = max(0, ys.min() - 4), min(mask.shape[0], ys.max() + 5)
    crop = mask[y1:y2, x1:x2]
    return cv2.resize(crop, None, fx=scale, fy=scale, interpolation=cv2.INTER_CUBIC)


def _read_player_name(outcome: np.ndarray, side: str) -> str:
    x1, y1, x2, y2 = _NAME_BOXES[side]
    baseline, suffix = _player_name_mask(outcome[y1:y2, x1:x2])
    name = _ocr_binary(baseline, 13)
    # Free-form names may contain spaces, hyphens, apostrophes, digits, etc. Keep
    # OCR text except for obvious leading/trailing punctuation artifacts.
    name = name.strip(' _-|[]()')
    if not name:
        raise ValueError(f'Could not OCR {side} player name')
    if suffix is not None:
        extra = re.sub(r'[^A-Za-z0-9]+', '', _ocr_binary(suffix, 7))
        if extra:
            name += extra
    return name


def _read_result(outcome: np.ndarray) -> str:
    x1, y1, x2, y2 = _RESULT_BOX
    crop = outcome[y1:y2, x1:x2]
    gray = cv2.cvtColor(crop, cv2.COLOR_BGR2GRAY)
    bw = cv2.threshold(gray, 175, 255, cv2.THRESH_BINARY)[1]
    bw = cv2.resize(bw, None, fx=3, fy=3, interpolation=cv2.INTER_CUBIC)
    text = re.sub(r'[^A-Z]', '', _ocr_binary(bw, 7).upper())
    if 'VICTORY' in text:
        return 'VICTORY'
    if 'DEFEAT' in text:
        return 'DEFEAT'
    raise ValueError(f'Unrecognized battle result: {text or "<blank>"}')


def extract_battle_metadata(image_path: Path | str) -> BattleMetadata:
    outcome = prepare_outcome(load_image(image_path))
    if outcome.shape[0] < 900 or outcome.shape[1] < 950:
        raise ValueError(f'Unexpected Outcome geometry for metadata OCR: {outcome.shape[:2]}')
    return BattleMetadata(
        attacker_name=_read_player_name(outcome, 'attacker'),
        defender_name=_read_player_name(outcome, 'defender'),
        result=_read_result(outcome),
    )
