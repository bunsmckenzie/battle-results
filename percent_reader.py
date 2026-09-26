"""Reusable fixed-UI percentage reader for troop ratios and combat bonuses.

Digit templates are learned from validated screenshots, but every value is read from
pixels at runtime.  Ratio slots are discovered from the percent signs, so a side may
contain two or three troop types without shifting the semantic mapping.
"""
from __future__ import annotations
from dataclasses import dataclass
from pathlib import Path
import cv2
import numpy as np
from layout import load_image
from troop_level_reader import TroopLevelRecognizer, card_centers, level_glyphs, tg_glyph

BONUS_LABELS=(
    'infantry_attack','infantry_defense','infantry_lethality','infantry_health',
    'cavalry_attack','cavalry_defense','cavalry_lethality','cavalry_health',
    'archer_attack','archer_defense','archer_lethality','archer_health')
TROOP_ORDER=('infantry','cavalry','archer')

@dataclass(frozen=True)
class PercentReading:
    value: float
    confidence: float

def _norm(patch:np.ndarray)->np.ndarray:
    ys,xs=np.where(patch>0)
    if not len(xs): return np.zeros((36,28),np.uint8)
    patch=patch[ys.min():ys.max()+1,xs.min():xs.max()+1]
    scale=min(24/patch.shape[1],32/patch.shape[0])
    r=cv2.resize(patch,(max(1,round(patch.shape[1]*scale)),max(1,round(patch.shape[0]*scale))),interpolation=cv2.INTER_NEAREST)
    out=np.zeros((36,28),np.uint8); y=(36-r.shape[0])//2; x=(28-r.shape[1])//2
    out[y:y+r.shape[0],x:x+r.shape[1]]=r
    return out

def _split_component(mask,x,y,w,h):
    p=mask[y:y+h,x:x+w]
    if w<=26: return [(x,_norm(p))]
    proj=(p>0).sum(axis=0); mid=w//2; lo=max(6,mid-7); hi=min(w-6,mid+8)
    cut=lo+int(np.argmin(proj[lo:hi]))
    return [(x+ox,_norm(q)) for ox,q in ((0,p[:,:cut]),(cut,p[:,cut:])) if q.shape[1]>=5]

def _bonus_components(image:np.ndarray,saturation:int):
    hsv=cv2.cvtColor(image,cv2.COLOR_BGR2HSV)
    mask=((hsv[:,:,1]>saturation)&(hsv[:,:,2]>100)).astype(np.uint8)*255
    _,_,stats,_=cv2.connectedComponentsWithStats(mask,8)
    return mask,stats

def _bonus_row_centers(image:np.ndarray):
    _,stats=_bonus_components(image,100)
    ys=sorted(int(y+h/2) for x,y,w,h,a in stats[1:]
              if 0.38*image.shape[0]<y<0.93*image.shape[0] and 23<=h<=28 and a>40 and (x<0.34*image.shape[1] or x>0.60*image.shape[1]))
    groups=[]
    for y in ys:
        if not groups or y-groups[-1][-1]>12: groups.append([y])
        else: groups[-1].append(y)
    centers=[round(sum(g)/len(g)) for g in groups if len(g)>=5]
    if len(centers)!=12: raise ValueError(f'Expected 12 bonus rows; detected {len(centers)}')
    return centers

def _bonus_glyphs(image,cy,xmin,xmax):
    for sat in (100,80):
        mask,stats=_bonus_components(image,sat); found=[]
        for x,y,w,h,a in stats[1:]:
            x,y,w,h,a=map(int,(x,y,w,h,a))
            if xmin<x<xmax and abs((y+h/2)-cy)<9 and 23<=h<=28 and 7<=w<=45 and a>70:
                found.extend(_split_component(mask,x,y,w,h))
        glyphs=[p for _,p in sorted(found)[:5]]
        if len(glyphs)==5: return glyphs
    raise ValueError('Could not segment five bonus digits')

def _ratio_groups(image,baseline):
    gray=cv2.cvtColor(image,cv2.COLOR_BGR2GRAY); mask=(gray<170).astype(np.uint8)*255
    _,_,stats,_=cv2.connectedComponentsWithStats(mask,8)
    percent_x=[]
    for x,y,w,h,a in stats[1:]:
        x,y,w,h,a=map(int,(x,y,w,h,a))
        if abs((y+h/2)-baseline)<15 and 18<=h<=24 and 17<=w<=23 and 50<=a<=100:
            percent_x.append(x)
    width=image.shape[1]; halves=((0.02*width,0.49*width),(0.51*width,0.995*width)); result=[]
    for lo,hi in halves:
        ends=sorted(x for x in percent_x if lo<x<hi); groups=[]; start=lo
        for end in ends:
            found=[]
            for x,y,w,h,a in stats[1:]:
                x,y,w,h,a=map(int,(x,y,w,h,a))
                if start<x<end and abs((y+h/2)-baseline)<15 and 19<=h<=24 and 5<=w<=45 and a>=80:
                    found.extend(_split_component(mask,x,y,w,h))
            groups.append([p for _,p in sorted(found)]); start=end+15
        result.append(groups)
    return result

class PercentDigitRecognizer:
    def __init__(self,template_path:Path|str|None=None):
        p=Path(template_path or Path(__file__).resolve().parent/'assets'/'percent_digits.npz'); d=np.load(p)
        self.bonus_images=d['bonus_images'].astype(np.float32)/255; self.bonus_labels=d['bonus_labels'].astype(int)
        # Ratio glyphs are slightly smaller, but bonus glyphs supply digits not yet seen in a ratio (notably 7).
        self.ratio_images=np.concatenate([d['ratio_images'].astype(np.float32)/255,self.bonus_images])
        self.ratio_labels=np.concatenate([d['ratio_labels'].astype(int),self.bonus_labels])
    def _digit(self,glyph,ratio=False):
        images=self.ratio_images if ratio else self.bonus_images; labels=self.ratio_labels if ratio else self.bonus_labels
        v=glyph.astype(np.float32)/255; dist=np.mean(np.abs(images-v),axis=(1,2)); j=int(np.argmin(dist))
        return int(labels[j]), max(0.0,1.0-float(dist[j])*2.5)
    def bonus(self,glyphs):
        pairs=[self._digit(g) for g in glyphs]; s=''.join(str(d) for d,_ in pairs)
        return PercentReading(float(s[:-1]+'.'+s[-1]),round(min(c for _,c in pairs),3))
    def ratio(self,glyphs):
        if not 3<=len(glyphs)<=5: raise ValueError(f'Unexpected ratio digit count: {len(glyphs)}')
        pairs=[self._digit(g,True) for g in glyphs]; s=''.join(str(d) for d,_ in pairs)
        return PercentReading(float(s[:-2]+'.'+s[-2:]),round(min(c for _,c in pairs),3))

def extract_ratios_bonuses(image_path:Path|str,recognizer:PercentDigitRecognizer|None=None,level_recognizer:TroopLevelRecognizer|None=None):
    image=load_image(image_path); rec=recognizer or PercentDigitRecognizer(); level_rec=level_recognizer or TroopLevelRecognizer(); rows=_bonus_row_centers(image); w=image.shape[1]
    bonuses={}
    for side,xmin,xmax in (('attacker',0.11*w,0.34*w),('defender',0.60*w,0.94*w)):
        for label,cy in zip(BONUS_LABELS,rows): bonuses[f'{side}.{label}']=rec.bonus(_bonus_glyphs(image,cy,xmin,xmax))
    ratio_groups=_ratio_groups(image,rows[0]-202); ratios={}
    for side,groups in zip(('attacker','defender'),ratio_groups):
        if not 1<=len(groups)<=3: raise ValueError(f'Expected 1-3 {side} ratio slots; detected {len(groups)}')
        centers=card_centers(side,len(groups),w); level_baseline=rows[0]-242
        for i,(glyphs,center) in enumerate(zip(groups,centers)):
            key=f'{side}.ratio.slot{i+1}'
            ratios[key]={'troop_type':TROOP_ORDER[i],'reading':rec.ratio(glyphs),
                         'troop_level':level_rec.troop_level(level_glyphs(image,center,level_baseline)),
                         'tg_level':level_rec.tg_level(tg_glyph(image,center,level_baseline))}
    return {'ratios':ratios,'bonuses':bonuses}
