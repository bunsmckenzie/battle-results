"""Deterministic reader for troop-card level badges in Ratios/Bonuses screenshots."""
from __future__ import annotations
from dataclasses import dataclass
from pathlib import Path
import cv2, numpy as np

@dataclass(frozen=True)
class LevelReading:
    value: float|int
    confidence: float

_CENTERS={'attacker':(0.103,0.241,0.379),'defender':(0.617,0.755,0.892)}

def card_centers(side:str,count:int,width:int):
    vals=_CENTERS[side]
    vals=vals[:count] if side=='attacker' else vals[3-count:]
    return [round(v*width) for v in vals]

def _norm(patch, shape=(28,22)):
    ys,xs=np.where(patch>0)
    if not len(xs): return np.zeros(shape,np.uint8)
    p=patch[ys.min():ys.max()+1,xs.min():xs.max()+1]
    scale=min((shape[1]-4)/p.shape[1],(shape[0]-4)/p.shape[0])
    r=cv2.resize(p,(max(1,round(p.shape[1]*scale)),max(1,round(p.shape[0]*scale))),interpolation=cv2.INTER_NEAREST)
    out=np.zeros(shape,np.uint8); y=(shape[0]-r.shape[0])//2; x=(shape[1]-r.shape[1])//2; out[y:y+r.shape[0],x:x+r.shape[1]]=r
    return out

def _white_mask(image):
    hsv=cv2.cvtColor(image,cv2.COLOR_BGR2HSV)
    return ((hsv[:,:,1]<105)&(hsv[:,:,2]>175)).astype(np.uint8)*255

def level_glyphs(image, center, level_baseline):
    """Return the three digits in Lv. NN.N (decimal point intentionally omitted)."""
    mask=_white_mask(image); x0=max(0,center-65); x1=min(image.shape[1],center+65)
    y0=max(0,level_baseline-4); y1=min(image.shape[0],level_baseline+28); m=mask[y0:y1,x0:x1]
    _,_,stats,_=cv2.connectedComponentsWithStats(m,8); found=[]
    for x,y,w,h,a in stats[1:]:
        x,y,w,h,a=map(int,(x,y,w,h,a))
        # Digits begin about 2 px right of card center; L/v are left of this.
        if 65<=x<=112 and 14<=h<=20 and 4<=w<=17 and a>=50:
            found.append((x,_norm(m[y:y+h,x:x+w])))
    found=[g for _,g in sorted(found)[:3]]
    if len(found)!=3: raise ValueError(f'Could not segment troop level at x={center}: expected 3 digits, got {len(found)}')
    return found

def tg_glyph(image, center, level_baseline):
    """Return the digit inside the gold upper-right troop-grade badge."""
    mask=_white_mask(image); x0=max(0,center+45); x1=min(image.shape[1],center+72)
    y0=max(0,level_baseline-112); y1=max(0,level_baseline-72); m=mask[y0:y1,x0:x1]
    _,_,stats,_=cv2.connectedComponentsWithStats(m,8); cand=[]
    for x,y,w,h,a in stats[1:]:
        x,y,w,h,a=map(int,(x,y,w,h,a))
        if 12<=h<=25 and 5<=w<=23 and a>=45: cand.append((a,_norm(m[y:y+h,x:x+w])))
    if not cand: raise ValueError(f'Could not segment TG level at x={center}')
    return max(cand,key=lambda z:z[0])[1]

class TroopLevelRecognizer:
    def __init__(self,template_path=None):
        p=Path(template_path or Path(__file__).resolve().parent/'assets'/'troop_level_digits.npz'); d=np.load(p)
        self.level_images=d['level_images'].astype(np.float32)/255; self.level_labels=d['level_labels'].astype(int)
        self.tg_images=d['tg_images'].astype(np.float32)/255; self.tg_labels=d['tg_labels'].astype(int)
    def _digit(self,glyph,kind):
        images,labels=(self.level_images,self.level_labels) if kind=='level' else (self.tg_images,self.tg_labels)
        v=glyph.astype(np.float32)/255; dist=np.mean(np.abs(images-v),axis=(1,2)); j=int(np.argmin(dist)); conf=max(0.,1-float(dist[j])*3)
        if conf<0.45: raise ValueError(f'Unrecognized troop {kind} digit (confidence={conf:.3f})')
        return int(labels[j]),conf
    def troop_level(self,glyphs):
        pairs=[self._digit(g,'level') for g in glyphs]; digits=''.join(str(d) for d,_ in pairs)
        return LevelReading(float(digits[:-1]+'.'+digits[-1]),round(min(c for _,c in pairs),3))
    def tg_level(self,glyph):
        d,c=self._digit(glyph,'tg'); return LevelReading(d,round(c,3))
