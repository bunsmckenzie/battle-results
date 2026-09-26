from dataclasses import dataclass
from pathlib import Path
from outcome_reader import extract_battle_outcome
from percent_reader import extract_ratios_bonuses
from battle_heroes import analyze_battle_heroes

@dataclass(frozen=True)
class Classification:
    image_type: str
    confidence: float
    detail: str = ''

def _try_outcome(path):
    try:
        r=extract_battle_outcome(path)
        if len(r)==12:
            return min(x.confidence for x in r.values())
    except Exception: pass
    return 0.0

def _try_rb(path):
    try:
        r=extract_ratios_bonuses(path)
        if len(r.get('bonuses',{}))==24 and len(r.get('ratios',{}))>=5:
            vals=[x.confidence for x in r['bonuses'].values()]
            vals += [x['reading'].confidence for x in r['ratios'].values()]
            return min(vals)
    except Exception: pass
    return 0.0

def _try_heroes(path):
    try:
        r=analyze_battle_heroes(path)
        if len(r)==6 and all(x.accepted for x in r.values()):
            return min(min(x.match_confidence,x.value_confidence) for x in r.values())
    except Exception: pass
    return 0.0

def classify_image(path, threshold=.50, margin=.10):
    scores={'outcome':_try_outcome(path),'ratios_bonuses':_try_rb(path),'heroes':_try_heroes(path)}
    ranked=sorted(scores.items(), key=lambda kv:kv[1], reverse=True)
    best,second=ranked[0],ranked[1]
    if best[1] < threshold or best[1]-second[1] < margin:
        return Classification('unknown', best[1], f'scores={scores}')
    return Classification(best[0], best[1], f'scores={scores}')

def classify_folder(folder):
    exts={'.jpg','.jpeg','.png','.webp','.bmp'}
    return {str(p):classify_image(p) for p in sorted(Path(folder).iterdir()) if p.is_file() and p.suffix.lower() in exts}
