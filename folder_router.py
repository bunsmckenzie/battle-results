"""Classify a folder of screenshots and resolve exactly one image per battle domain."""
from pathlib import Path
from screenshot_classifier import classify_folder

REQUIRED_TYPES = ('outcome', 'heroes', 'ratios_bonuses')


def resolve_battle_images(folder):
    results = classify_folder(folder)
    if not results:
        raise ValueError(f'No supported image files found in folder: {folder}')

    by_type = {kind: [] for kind in REQUIRED_TYPES}
    unknown = []
    for path, result in results.items():
        if result.image_type in by_type:
            by_type[result.image_type].append((path, result))
        else:
            unknown.append((path, result))

    problems = []
    for kind in REQUIRED_TYPES:
        matches = by_type[kind]
        if not matches:
            problems.append(f'missing {kind} image')
        elif len(matches) > 1:
            names = ', '.join(Path(p).name for p, _ in matches)
            problems.append(f'multiple {kind} images: {names}')

    # Unknown extras are allowed only when all required domains resolve uniquely.
    # They are not silently substituted for a missing/duplicate required image.
    if problems:
        if unknown:
            names = ', '.join(Path(p).name for p, _ in unknown)
            problems.append(f'unknown image(s): {names}')
        raise ValueError('Cannot resolve battle folder: ' + '; '.join(problems))

    return {kind: by_type[kind][0][0] for kind in REQUIRED_TYPES}
