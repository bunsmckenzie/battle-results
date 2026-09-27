-- Step 11: human-readable player names and battle result from Battle Overview.
-- Existing battles remain valid and receive NULL metadata until reprocessed.
ALTER TABLE battles ADD COLUMN attacker_name TEXT;
ALTER TABLE battles ADD COLUMN defender_name TEXT;
ALTER TABLE battles ADD COLUMN result TEXT CHECK (result IS NULL OR result IN ('VICTORY','DEFEAT'));
