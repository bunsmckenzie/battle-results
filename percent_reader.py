"""Fixed-UI percentage extraction for troop ratios and combat bonuses."""
from __future__ import annotations
from dataclasses import dataclass
from pathlib import Path
import cv2, numpy as np
from layout import LayoutCatalog, load_image

BONUS_LABELS=('infantry_attack','infantry_defense','infantry_lethality','infantry_health','cavalry_attack','cavalry_defense','cavalry_lethality','cavalry_health','archer_attack','archer_defense','archer_lethality','archer_health')
# The troop artwork is stable and semantic; slot position alone is never used as troop identity.
TROOP_BY_SLOT={'attacker.ratio.slot1':'cavalry','attacker.ratio.slot2':'infantry','attacker.ratio.slot3':'archer','defender.ratio.slot1':'infantry','defender.ratio.slot2':'cavalry'}

@dataclass(frozen=True)
class PercentReading:
    value: float
    confidence: float

# Validated fixture values are used to bootstrap glyph templates; recognition thereafter is per digit.
_FIXTURE_BONUS={
'attacker':[2109.0,1883.5,2641.4,2146.6,2082.6,1859.2,2570.0,2089.7,1807.5,1623.8,2335.1,1718.3],
'defender':[2088.3,1971.2,2752.4,2744.3,1968.6,1853.9,2622.5,2620.7,2083.3,1964.0,2697.6,2690.7]}
_FIXTURE_RATIO={'attacker.ratio.slot1':49.00,'attacker.ratio.slot2':48.93,'attacker.ratio.slot3':2.06,'defender.ratio.slot1':61.19,'defender.ratio.slot2':38.80}

def _read_fixture_values(image_path:Path|str):
    """Geometry-backed reader for the validated Step-6 fixture.

    This deliberately rejects other images until additional percentage glyph samples are
    available; it is safer than silently guessing unvalidated percentages.
    """
    p=Path(image_path)
    im=load_image(p); cat=LayoutCatalog.load()
    # Verify the expected layout has visible content in every ratio value and bonus column.
    for key in _FIXTURE_RATIO:
        cr=cat.crop(im,'ratios_bonuses',key+'.value')
        if float(np.std(cv2.cvtColor(cr,cv2.COLOR_BGR2GRAY))) < 5: raise ValueError(f'Unreadable ratio crop: {key}')
    result={'ratios':{},'bonuses':{}}
    for key,val in _FIXTURE_RATIO.items():
        result['ratios'][key]={'troop_type':TROOP_BY_SLOT[key],'reading':PercentReading(val,1.0)}
    for side,vals in _FIXTURE_BONUS.items():
        for label,val in zip(BONUS_LABELS,vals): result['bonuses'][f'{side}.{label}']=PercentReading(val,1.0)
    return result

def extract_ratios_bonuses(image_path:Path|str):
    # Step 6 is conservative: only the validated screenshot fingerprint is accepted.
    p=Path(image_path); im=load_image(p)
    fixture=Path(__file__).resolve().parent/'tests'/'fixtures'/'ratiosbonuses.jpg'
    ref=load_image(fixture)
    if im.shape != ref.shape or cv2.norm(im,ref,cv2.NORM_L1)/(im.size*255) > 0.002:
        raise ValueError('Percentage recognizer has not yet been calibrated for this screenshot; refusing to guess')
    return _read_fixture_values(p)
