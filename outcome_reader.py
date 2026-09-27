"""Deterministic reader for the fixed Battle Overview numeric fields."""
from __future__ import annotations
from dataclasses import dataclass
from pathlib import Path
import cv2
import numpy as np
from layout import LayoutCatalog, load_image
from screenshot_preprocessor import prepare_outcome

FIELDS = ('power','squad','losses','injured','lightly_injured','residents')
SIDES = ('attacker','defender')

@dataclass(frozen=True)
class OutcomeReading:
    value: int
    confidence: float


def _binary(crop: np.ndarray) -> np.ndarray:
    g=cv2.cvtColor(crop, cv2.COLOR_BGR2GRAY) if crop.ndim==3 else crop
    return cv2.threshold(g, 190, 255, cv2.THRESH_BINARY_INV)[1]


def _glyphs(crop: np.ndarray):
    bw=_binary(crop)
    n, labels, stats, _=cv2.connectedComponentsWithStats(bw,8)
    out=[]
    for i in range(1,n):
        x,y,w,h,a=map(int,stats[i])
        # Numeric glyphs are the tall components. Ignore commas, minus and power icon.
        if 16 <= h <= 32 and 7 <= w <= 28 and a >= 60:
            patch=bw[y:y+h,x:x+w]
            out.append((x,_norm(patch)))
        elif 16 <= h <= 32 and 29 <= w <= 95 and a >= 120:
            # Antialiasing can join two or even three adjacent digits after a
            # full-screen capture is resized to canonical geometry.  Estimate
            # the digit count from width, then split near equal-width valleys.
            patch=bw[y:y+h,x:x+w]
            count=max(2,min(4,round(w/22)))
            cuts=[]
            proj=(patch>0).sum(axis=0)
            prev=0
            for part in range(1,count):
                target=round(w*part/count)
                lo=max(prev+6,target-6); hi=min(w-6,target+7)
                if hi<=lo: continue
                cut=lo+int(np.argmin(proj[lo:hi])); cuts.append(cut); prev=cut
            starts=[0]+cuts; ends=cuts+[w]
            for start,end in zip(starts,ends):
                q=patch[:,start:end]
                if q.shape[1]>=5: out.append((x+start,_norm(q)))
    return [p for _,p in sorted(out,key=lambda z:z[0])]


def _norm(patch: np.ndarray) -> np.ndarray:
    ys,xs=np.where(patch>0)
    if len(xs)==0: return np.zeros((36,28),np.uint8)
    patch=patch[ys.min():ys.max()+1,xs.min():xs.max()+1]
    scale=min(24/patch.shape[1],32/patch.shape[0])
    r=cv2.resize(patch,(max(1,round(patch.shape[1]*scale)),max(1,round(patch.shape[0]*scale))),interpolation=cv2.INTER_NEAREST)
    canvas=np.zeros((36,28),np.uint8); y=(36-r.shape[0])//2; x=(28-r.shape[1])//2
    canvas[y:y+r.shape[0],x:x+r.shape[1]]=r
    return canvas


class OutcomeDigitRecognizer:
    def __init__(self, template_path: Path|str|None=None):
        template_path=Path(template_path or Path(__file__).resolve().parent/'assets'/'outcome_digits.npz')
        data=np.load(template_path)
        self.images=data['images'].astype(np.float32)/255.0
        self.labels=data['labels'].astype(int)

    def read(self,crop:np.ndarray)->OutcomeReading:
        glyphs=_glyphs(crop)
        if not glyphs: raise ValueError('No numeric glyphs found in outcome crop')
        digits=[]; conf=[]
        for g in glyphs:
            v=g.astype(np.float32).reshape(1,-1)/255.0
            t=self.images.reshape(len(self.images),-1)
            # normalized mismatch; nearest validated glyph wins
            d=np.mean(np.abs(t-v),axis=1)
            j=int(np.argmin(d)); digits.append(str(self.labels[j])); conf.append(max(0.0,1.0-float(d[j])*2.5))
        return OutcomeReading(int(''.join(digits)), float(min(conf)))


def extract_battle_outcome(image_path:Path|str, recognizer:OutcomeDigitRecognizer|None=None):
    image=prepare_outcome(load_image(image_path)); cat=LayoutCatalog.load(); recognizer=recognizer or OutcomeDigitRecognizer()
    result={}
    for side in SIDES:
        for field in FIELDS:
            key=f'{side}.{field}'; reading=recognizer.read(cat.crop(image,'outcome',key))
            if field == 'power':
                # Preserve the sign shown in the screenshot.
                bw = _binary(cat.crop(image, 'outcome', key))
                n, _, stats, _ = cv2.connectedComponentsWithStats(bw, 8)
                has_minus = any(int(w) >= 8 and int(h) <= 6 and int(a) >= 15 for x,y,w,h,a in stats[1:])
                if has_minus:
                    reading = OutcomeReading(-reading.value, reading.confidence)
            result[key]=reading
    return result
