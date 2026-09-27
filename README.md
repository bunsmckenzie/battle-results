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

## Step 9.1: full-screen routing and troop-count view

Batch folders may contain full Kingshot report screenshots in any filename/order. The
router normalizes supported full-screen captures before reading the Outcome and Hero
Comparison sections. Ratios/Bonuses accepts either percentage labels or the game's
troop-count display; in count mode it derives each side's troop percentages from the
visible troop counts and still reads troop_level and tg_level from the troop cards.

## Step 10: Battle identity and duplicate protection

Full Outcome screenshots now provide a stable logical identity from the report header:

- battle timestamp
- X coordinate
- Y coordinate
- normalized `battle_identity` key, e.g. `2026-09-26T09:56:21@597,597`

Migration `005_battle_identity.sql` stores these fields on `battles` and adds a unique index for non-null identities. Legacy cropped Outcome images remain supported but cannot provide header identity and therefore retain NULL identity fields.

Batch dry-run and real ingestion report duplicates separately and do not insert them. Dry-run does not modify the database, including when checking a Step 9.1 database that predates the identity migration.

## Step 11: player names and result

The Outcome panel now stores three human-readable fields on each battle:

- `attacker_name` — alliance tag removed before OCR
- `defender_name` — alliance tag removed before OCR
- `result` — normalized to `VICTORY` or `DEFEAT`

Free-form player names use Tesseract OCR. Tesseract must be installed locally and
available as `tesseract` on PATH. On Windows the reader also checks the common
`C:\Program Files\Tesseract-OCR\tesseract.exe` installation path.

Verify the OCR prerequisite with:

```powershell
tesseract --version
```

Inspect metadata before ingesting with:

```powershell
python app.py read-battle-metadata --image tests/fixtures/outcome.jpg
```

`batch-ingest --dry-run` validates metadata OCR as part of preflight, so a battle is
not reported READY if its player names or result cannot be read conservatively.
Migration `006_battle_metadata.sql` preserves existing battles with NULL metadata;
reprocess old battles if you want these fields populated.

## Step 12: Tableau reporting views

`python app.py init-db` now creates four read-only SQLite views for analytics while leaving the normalized ingestion tables unchanged:

- `vw_battle_summary` — one wide row per battle.
- `vw_battle_troops` — six side/troop rows per battle.
- `vw_battle_bonuses` — twenty-four side/troop/stat rows per battle.
- `vw_battle_heroes` — lead and joiner hero rows with hero reference attributes.

Preview them from the command line, for example:

```powershell
python app.py preview-view --view summary --limit 5
python app.py preview-view --view troops --limit 12
python app.py preview-view --view bonuses --limit 24
python app.py preview-view --view heroes --limit 20
```

The views are intended as the stable analysis interface for Tableau. Connect Tableau to the same `battle_data.sqlite3` database through your chosen SQLite-capable connector and use the `vw_*` objects rather than rebuilding the normalized joins in each workbook.
