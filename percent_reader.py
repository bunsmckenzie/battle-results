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
from screenshot_preprocessor import prepare_ratios_bonuses
from troop_level_reader import TroopLevelRecognizer, card_centers, level_glyphs, tg_glyph
from outcome_reader import OutcomeDigitRecognizer, _binary as _count_binary, _norm as _count_norm

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




def _troop_count_glyphs(crop):
    """Segment absolute troop counts from the small text below troop cards.

    At some resize phases, adjacent count digits merge into 2- or 3-digit
    connected components. Their rendered digit width is about 16 px at canonical
    size, which is narrower than the Battle Overview number font.
    """
    bw=_count_binary(crop)
    _,_,stats,_=cv2.connectedComponentsWithStats(bw,8)
    out=[]
    for x,y,w,h,a in stats[1:]:
        x,y,w,h,a=map(int,(x,y,w,h,a))
        if not (16<=h<=32 and 7<=w<=95 and a>=60):
            continue
        patch=bw[y:y+h,x:x+w]
        if w<27:
            out.append((x,_count_norm(patch)))
            continue
        count=max(2,min(5,round(w/16)))
        proj=(patch>0).sum(axis=0); cuts=[]; prev=0
        for part in range(1,count):
            target=round(w*part/count)
            lo=max(prev+5,target-5); hi=min(w-5,target+6)
            if hi<=lo:
                continue
            cut=lo+int(np.argmin(proj[lo:hi])); cuts.append(cut); prev=cut
        starts=[0]+cuts; ends=cuts+[w]
        for start,end in zip(starts,ends):
            q=patch[:,start:end]
            if q.shape[1]>=4:
                out.append((x+start,_count_norm(q)))
    return [g for _,g in sorted(out,key=lambda z:z[0])]

def _read_troop_count(crop, rec):
    glyphs=_troop_count_glyphs(crop)
    if not 4<=len(glyphs)<=8:
        raise ValueError(f'Unexpected troop-count digit count: {len(glyphs)}')
    images=rec.images.reshape(len(rec.images),-1)
    digits=[]; conf=[]
    for glyph in glyphs:
        v=glyph.astype(np.float32).reshape(1,-1)/255.0
        dist=np.mean(np.abs(images-v),axis=1); j=int(np.argmin(dist))
        digits.append(str(rec.labels[j])); conf.append(max(0.0,1.0-float(dist[j])*2.5))
    return int(''.join(digits)),float(min(conf))

def ratios_from_counts(counts):
    """Convert visible absolute troop counts to percentages, rounded to 2 decimals."""
    values=[int(v) for v in counts]
    total=sum(values)
    if total <= 0:
        raise ValueError(f'Invalid troop-count total: {total}')
    return [round(v*100.0/total,2) for v in values]




def _read_tg_near(image, center, level_baseline, level_rec):
    """Read a TG badge near the expected card center.

    Try the calibrated location first. Only if that fails, search a tightly
    bounded set of offsets used by resized two-card layouts. The recognizer's
    existing confidence threshold is never lowered.
    """
    for offset in (0,-12,-16,-8,8,12,16):
        try:
            return level_rec.tg_level(tg_glyph(image,center+offset,level_baseline))
        except ValueError:
            continue
    raise ValueError(f'Could not confidently read TG level near x={center}')

def _count_mode_slots(image, baseline, level_baseline, level_rec):
    """Read troop counts shown under cards and derive per-side percentages.

    The game can toggle the Troop Power Comparison between percentage labels and
    absolute troop counts.  Counts are semantically equivalent for our ratio field,
    so derive percentages from the visible side total rather than rejecting the
    screenshot.
    """
    rec=OutcomeDigitRecognizer(); w=image.shape[1]; result={}
    for side in ('attacker','defender'):
        visible=[]
        for center in card_centers(side,3,w):
            x0=max(0,center-75); x1=min(w,center+75)
            crop=image[max(0,baseline-10):min(image.shape[0],baseline+38),x0:x1]
            try:
                count_value,count_confidence=_read_troop_count(crop,rec)
            except ValueError:
                continue
            if count_confidence < 0.45:
                continue
            from outcome_reader import OutcomeReading
            visible.append((center,OutcomeReading(count_value,count_confidence)))
        if not 1 <= len(visible) <= 3:
            raise ValueError(f'Expected 1-3 {side} troop-count slots; detected {len(visible)}')
        ratios=ratios_from_counts([r.value for _,r in visible])
        for i,((center,count_reading),ratio) in enumerate(zip(visible,ratios)):
            reading=PercentReading(ratio,round(count_reading.confidence,3))
            result[f'{side}.ratio.slot{i+1}']={
                'troop_type':TROOP_ORDER[i], 'reading':reading,
                'troop_level':level_rec.troop_level(level_glyphs(image,center,level_baseline)),
                'tg_level':_read_tg_near(image,center,level_baseline,level_rec),
            }
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
    image=prepare_ratios_bonuses(load_image(image_path)); rec=recognizer or PercentDigitRecognizer(); level_rec=level_recognizer or TroopLevelRecognizer(); rows=_bonus_row_centers(image); w=image.shape[1]
    bonuses={}
    for side,xmin,xmax in (('attacker',0.11*w,0.34*w),('defender',0.60*w,0.94*w)):
        for label,cy in zip(BONUS_LABELS,rows): bonuses[f'{side}.{label}']=rec.bonus(_bonus_glyphs(image,cy,xmin,xmax))
    ratio_baseline=rows[0]-202; level_baseline=rows[0]-242
    ratio_groups=_ratio_groups(image,ratio_baseline); ratios={}
    if any(ratio_groups):
        ratio_input_mode='ratios'
        for side,groups in zip(('attacker','defender'),ratio_groups):
            if not 1<=len(groups)<=3: raise ValueError(f'Expected 1-3 {side} ratio slots; detected {len(groups)}')
            centers=card_centers(side,len(groups),w)
            for i,(glyphs,center) in enumerate(zip(groups,centers)):
                key=f'{side}.ratio.slot{i+1}'
                ratios[key]={'troop_type':TROOP_ORDER[i],'reading':rec.ratio(glyphs),
                             'troop_level':level_rec.troop_level(level_glyphs(image,center,level_baseline)),
                             'tg_level':_read_tg_near(image,center,level_baseline,level_rec)}
    else:
        ratio_input_mode='counts'
        ratios=_count_mode_slots(image,ratio_baseline,level_baseline,level_rec)
    return {'ratio_input_mode':ratio_input_mode,'ratios':ratios,'bonuses':bonuses}
