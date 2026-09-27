-- Step 10: stable logical battle identity from the Outcome report header.
-- Existing battles remain valid; legacy cropped Outcome screenshots cannot be backfilled automatically.
ALTER TABLE battles ADD COLUMN battle_timestamp TEXT;
ALTER TABLE battles ADD COLUMN coord_x INTEGER;
ALTER TABLE battles ADD COLUMN coord_y INTEGER;
ALTER TABLE battles ADD COLUMN battle_identity TEXT;
CREATE UNIQUE INDEX IF NOT EXISTS idx_battles_battle_identity
    ON battles(battle_identity)
    WHERE battle_identity IS NOT NULL;
