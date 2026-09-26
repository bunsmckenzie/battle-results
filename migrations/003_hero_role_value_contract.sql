-- Lead heroes require a 0-10 join value. Joiners are name-only and must have NULL join_value.
PRAGMA foreign_keys=OFF;
ALTER TABLE battle_heroes RENAME TO battle_heroes_old;
CREATE TABLE battle_heroes (
    battle_id INTEGER NOT NULL REFERENCES battles(battle_id) ON DELETE CASCADE,
    side TEXT NOT NULL CHECK (side IN ('attacker','defender')),
    role TEXT NOT NULL CHECK (role IN ('lead','joiner')),
    slot INTEGER NOT NULL CHECK (slot >= 1),
    hero_id INTEGER NOT NULL REFERENCES heroes(hero_id),
    join_value INTEGER CHECK (
        (role='lead' AND join_value IS NOT NULL AND join_value BETWEEN 0 AND 10) OR
        (role='joiner' AND join_value IS NULL)
    ),
    match_confidence REAL CHECK (match_confidence IS NULL OR (match_confidence >= 0 AND match_confidence <= 1)),
    ocr_confidence REAL CHECK (ocr_confidence IS NULL OR (ocr_confidence >= 0 AND ocr_confidence <= 1)),
    PRIMARY KEY (battle_id, side, role, slot)
);
INSERT INTO battle_heroes(battle_id,side,role,slot,hero_id,join_value,match_confidence,ocr_confidence)
SELECT battle_id,side,role,slot,hero_id,
       CASE WHEN role='joiner' THEN NULL ELSE join_value END,
       match_confidence,ocr_confidence
FROM battle_heroes_old;
DROP TABLE battle_heroes_old;
CREATE INDEX idx_battle_heroes_hero_id ON battle_heroes(hero_id);
PRAGMA foreign_keys=ON;
