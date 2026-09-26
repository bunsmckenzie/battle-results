-- Step 7 relationship model. These child tables had not yet been used for ingestion;
-- rebuild them around side/type rows before the first persisted battle.
ALTER TABLE battles ADD COLUMN battle_key TEXT;
ALTER TABLE battles ADD COLUMN outcome_image TEXT;
ALTER TABLE battles ADD COLUMN heroes_image TEXT;
ALTER TABLE battles ADD COLUMN ratios_bonuses_image TEXT;
ALTER TABLE battles ADD COLUMN notes TEXT;
CREATE UNIQUE INDEX IF NOT EXISTS idx_battles_battle_key ON battles(battle_key);

DROP TABLE IF EXISTS battle_heroes;
DROP TABLE IF EXISTS troop_bonuses;
DROP TABLE IF EXISTS troop_ratios;
DROP TABLE IF EXISTS battle_outcomes;

CREATE TABLE battle_outcomes (
    battle_id INTEGER NOT NULL REFERENCES battles(battle_id) ON DELETE CASCADE,
    side TEXT NOT NULL CHECK (side IN ('attacker','defender')),
    power INTEGER,
    squad INTEGER NOT NULL CHECK (squad >= 0),
    losses INTEGER NOT NULL CHECK (losses >= 0),
    injured INTEGER NOT NULL CHECK (injured >= 0),
    lightly_injured INTEGER NOT NULL CHECK (lightly_injured >= 0),
    residents INTEGER NOT NULL CHECK (residents >= 0),
    PRIMARY KEY (battle_id, side)
);

CREATE TABLE troop_ratios (
    battle_id INTEGER NOT NULL REFERENCES battles(battle_id) ON DELETE CASCADE,
    side TEXT NOT NULL CHECK (side IN ('attacker','defender')),
    troop_type TEXT NOT NULL CHECK (troop_type IN ('infantry','cavalry','archer')),
    ratio REAL NOT NULL CHECK (ratio >= 0 AND ratio <= 100),
    was_present INTEGER NOT NULL DEFAULT 1 CHECK (was_present IN (0,1)),
    confidence REAL CHECK (confidence IS NULL OR (confidence >= 0 AND confidence <= 1)),
    PRIMARY KEY (battle_id, side, troop_type)
);

CREATE TABLE troop_bonuses (
    battle_id INTEGER NOT NULL REFERENCES battles(battle_id) ON DELETE CASCADE,
    side TEXT NOT NULL CHECK (side IN ('attacker','defender')),
    troop_type TEXT NOT NULL CHECK (troop_type IN ('infantry','cavalry','archer')),
    stat TEXT NOT NULL CHECK (stat IN ('attack','defense','lethality','health')),
    value REAL NOT NULL,
    confidence REAL CHECK (confidence IS NULL OR (confidence >= 0 AND confidence <= 1)),
    PRIMARY KEY (battle_id, side, troop_type, stat)
);

CREATE TABLE battle_heroes (
    battle_id INTEGER NOT NULL REFERENCES battles(battle_id) ON DELETE CASCADE,
    side TEXT NOT NULL CHECK (side IN ('attacker','defender')),
    role TEXT NOT NULL CHECK (role IN ('lead','joiner')),
    slot INTEGER NOT NULL CHECK (slot >= 1),
    hero_id INTEGER NOT NULL REFERENCES heroes(hero_id),
    join_value INTEGER NOT NULL CHECK (join_value BETWEEN 0 AND 10),
    match_confidence REAL CHECK (match_confidence IS NULL OR (match_confidence >= 0 AND match_confidence <= 1)),
    ocr_confidence REAL CHECK (ocr_confidence IS NULL OR (ocr_confidence >= 0 AND ocr_confidence <= 1)),
    PRIMARY KEY (battle_id, side, role, slot)
);
CREATE INDEX idx_battle_heroes_hero_id ON battle_heroes(hero_id);
