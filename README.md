# Battle OCR → SQLite

Starter pipeline for fixed-layout game screenshots.

Domains:
- Outcome: Power, Squad, Losses, Injured, Lightly Injured, Residents
- Troop ratios: Infantry, Cavalry, Archer
- Bonuses: Infantry/Cavalry/Archer × Attack/Defense/Lethality/Health
- Heroes: 22-hero reference catalog plus battle hero join value (0–10)

The pipeline is deliberately split into image extraction, validation, and database insertion. The screenshot coordinates are configuration-driven so we can calibrate them against your final cleaned crops.

## Install

Python 3.10+ is recommended.

```bash
python -m venv .venv
# Windows
.venv\\Scripts\\activate
# macOS/Linux
# source .venv/bin/activate
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
```


PaddleOCR is not required for the validated hero matching/join-value path.

## Initialize database

```bash
python app.py init-db
python app.py seed-heroes
```

This creates `battle_data.sqlite3` and loads the 22 known heroes. Database schema changes live in `migrations/` and are recorded in `schema_migrations`, so initialization is safe to run repeatedly.

## Run database tests

```bash
python -m unittest discover -s tests -v
```

## Next calibration step

Replace the placeholder normalized coordinates in `config/layout.example.json` with the exact regions from the final fixed crops. Then we can wire those regions into the OCR extractor and add the hero image matcher.

The intended transaction flow is:

image → fixed regions → OCR/image matching → normalization → validation → SQLite transaction

A failed validation must not create a partial battle record.

## Step 2: screenshot geometry

`config/layout.json` contains normalized (resolution-independent) regions for the three
current screenshot types.  `layout.py` converts those regions to pixel crops.  This
stage intentionally performs no OCR.

Visually inspect any layout with:

```bash
python app.py debug-layout --type hero_comparison --image tests/fixtures/herocomparison.jpg --out debug_crops/heroes
python app.py debug-layout --type outcome --image tests/fixtures/outcome.jpg --out debug_crops/outcome
python app.py debug-layout --type ratios_bonuses --image tests/fixtures/ratiosbonuses.jpg --out debug_crops/ratiosbonuses
```

Run all tests with:

```bash
python -m unittest discover -s tests -v
```

## Step 3: conservative hero matching

Hero portraits can be checked against `assets/heroes/hero_lookup.png` without OCR:

```bash
python app.py match-heroes --image tests/fixtures/herocomparison.jpg
```

The matcher uses SIFT local image features and intentionally returns `UNKNOWN` when the evidence is weak. This matters because the battle UI can show alternate hero artwork/skins that differ from the default lookup portrait. An `UNKNOWN` result must be reviewed or resolved from an expanded reference catalog; it must not be silently converted to the nearest candidate.

Run all tests with:

```bash
python -m unittest discover -s tests -v
```

## Step 4.1: constrained hero join-value recognition

Read only the top-most adjacent equipment value for each of the six battle heroes:

```bash
python app.py read-hero-values --image tests/fixtures/herocomparison.jpg
```

Only integer values from 0 through 10 are valid. The current real fixture contains six +10 values, so +10 is positively recognized with OpenCV glyph geometry and no Paddle dependency. Unvalidated single-digit glyphs (0–9) are rejected as UNKNOWN rather than guessed; add labeled real screenshots for those values as they become available.

## Step 8: Manual joining heroes

Joining heroes are attached to an existing battle without changing its lead heroes or extracted battle data.

```bash
python app.py add-joiner B000001 --side attacker --hero "Charles" --value 8
python app.py show-battle B000001
python app.py remove-joiner B000001 --side attacker --slot 1
```

Join values must be integers from 0 through 10. Hero names are validated against the seeded hero catalog. Joiner slots are assigned independently for attacker and defender.
