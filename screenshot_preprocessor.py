"""Normalize full Kingshot report screenshots into the domain views used by readers.

Older fixtures are already cropped (Outcome/Heroes) or are 1080x2340 full-screen
(Ratios/Bonuses). Real end-user screenshots may arrive as full-screen captures at
other resolutions and at different vertical scroll positions. Normalize them to
canonical geometry and, for panel readers, anchor the crop to static UI structure.
"""
from __future__ import annotations
from pathlib import Path
import cv2
import numpy as np

CANONICAL_SIZE=(1080,2340)  # width, height
FULL_ASPECT=1080/2340
_BASE_DIR=Path(__file__).resolve().parent
_HERO_HEADER_TEMPLATE=_BASE_DIR/'assets'/'hero_comparison_header.png'
_HERO_TEMPLATE_TOP=680
_HERO_CROP_TOP=690
_HERO_CROP_HEIGHT=794
_HERO_SEARCH_Y=(450,1200)
_HERO_MIN_TEMPLATE_CONFIDENCE=.75


def is_full_report(image: np.ndarray) -> bool:
    if image is None or image.ndim < 2:
        return False
    h,w=image.shape[:2]
    return h >= 1500 and abs((w/h)-FULL_ASPECT) <= 0.02


def normalize_full_report(image: np.ndarray) -> np.ndarray:
    if not is_full_report(image):
        return image
    if (image.shape[1],image.shape[0]) == CANONICAL_SIZE:
        return image
    return cv2.resize(image,CANONICAL_SIZE,interpolation=cv2.INTER_CUBIC)


def prepare_outcome(image: np.ndarray) -> np.ndarray:
    if not is_full_report(image):
        return image
    image=normalize_full_report(image)
    # Canonical Battle Overview crop, aligned to the validated 1001x955 fixture.
    return image[501:1456,41:1042].copy()


def _locate_hero_crop_top(image: np.ndarray) -> int:
    """Locate the static Hero Comparison title and return the canonical panel crop top.

    The battle report is scrollable, so full-screen Hero screenshots can place the
    panel at different absolute Y positions. Matching only the static centered title
    keeps routing independent of hero artwork, filenames, and screenshot order.
    """
    template=cv2.imread(str(_HERO_HEADER_TEMPLATE),cv2.IMREAD_GRAYSCALE)
    if template is None:
        return _HERO_CROP_TOP
    gray=cv2.cvtColor(image,cv2.COLOR_BGR2GRAY)
    y1,y2=_HERO_SEARCH_Y
    search=gray[y1:y2,250:830]
    th,tw=template.shape[:2]
    if search.shape[0] < th or search.shape[1] < tw:
        return _HERO_CROP_TOP
    result=cv2.matchTemplate(search,template,cv2.TM_CCOEFF_NORMED)
    _,score,_,loc=cv2.minMaxLoc(result)
    if score < _HERO_MIN_TEMPLATE_CONFIDENCE:
        return _HERO_CROP_TOP
    title_top=y1+loc[1]
    top=title_top+(_HERO_CROP_TOP-_HERO_TEMPLATE_TOP)
    return max(0,min(top,image.shape[0]-_HERO_CROP_HEIGHT))


def prepare_heroes(image: np.ndarray) -> np.ndarray:
    if not is_full_report(image):
        return image
    image=normalize_full_report(image)
    top=_locate_hero_crop_top(image)
    return image[top:top+_HERO_CROP_HEIGHT,0:1080].copy()


def prepare_ratios_bonuses(image: np.ndarray) -> np.ndarray:
    return normalize_full_report(image)
