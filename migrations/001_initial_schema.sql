CREATE TABLE IF NOT EXISTS schema_migrations (
    version TEXT PRIMARY KEY,
    applied_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS heroes (
    hero_id INTEGER PRIMARY KEY,
    name TEXT NOT NULL UNIQUE,
    generation INTEGER NOT NULL CHECK (generation >= 1),
    troop_type TEXT NOT NULL CHECK (troop_type IN ('infantry', 'cavalry', 'archer'))
);

CREATE TABLE IF NOT EXISTS battles (
    battle_id INTEGER PRIMARY KEY,
    source_image TEXT,
    captured_at TEXT,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS battle_outcomes (
    battle_id INTEGER PRIMARY KEY REFERENCES battles(battle_id) ON DELETE CASCADE,
    power INTEGER CHECK (power IS NULL OR power >= 0),
    squad INTEGER CHECK (squad IS NULL OR squad >= 0),
    losses INTEGER CHECK (losses IS NULL OR losses >= 0),
    injured INTEGER CHECK (injured IS NULL OR injured >= 0),
    lightly_injured INTEGER CHECK (lightly_injured IS NULL OR lightly_injured >= 0),
    residents INTEGER CHECK (residents IS NULL OR residents >= 0)
);

CREATE TABLE IF NOT EXISTS troop_ratios (
    battle_id INTEGER PRIMARY KEY REFERENCES battles(battle_id) ON DELETE CASCADE,
    infantry REAL NOT NULL CHECK (infantry >= 0 AND infantry <= 100),
    cavalry REAL NOT NULL CHECK (cavalry >= 0 AND cavalry <= 100),
    archer REAL NOT NULL CHECK (archer >= 0 AND archer <= 100),
    CHECK (ABS((infantry + cavalry + archer) - 100.0) <= 0.2)
);

CREATE TABLE IF NOT EXISTS troop_bonuses (
    battle_id INTEGER NOT NULL REFERENCES battles(battle_id) ON DELETE CASCADE,
    troop_type TEXT NOT NULL CHECK (troop_type IN ('infantry', 'cavalry', 'archer')),
    attack REAL NOT NULL,
    defense REAL NOT NULL,
    lethality REAL NOT NULL,
    health REAL NOT NULL,
    PRIMARY KEY (battle_id, troop_type)
);

CREATE TABLE IF NOT EXISTS battle_heroes (
    battle_id INTEGER NOT NULL REFERENCES battles(battle_id) ON DELETE CASCADE,
    slot INTEGER NOT NULL CHECK (slot >= 1),
    hero_id INTEGER NOT NULL REFERENCES heroes(hero_id),
    join_value INTEGER NOT NULL CHECK (join_value BETWEEN 0 AND 10),
    match_confidence REAL CHECK (match_confidence IS NULL OR (match_confidence >= 0 AND match_confidence <= 1)),
    ocr_confidence REAL CHECK (ocr_confidence IS NULL OR (ocr_confidence >= 0 AND ocr_confidence <= 1)),
    PRIMARY KEY (battle_id, slot),
    UNIQUE (battle_id, hero_id)
);

CREATE INDEX IF NOT EXISTS idx_battle_heroes_hero_id ON battle_heroes(hero_id);
