-- Step 12: Tableau/reporting layer. These views do not change normalized storage.

CREATE VIEW IF NOT EXISTS vw_battle_summary AS
SELECT
    b.battle_id,
    b.battle_key,
    b.battle_timestamp,
    b.attacker_name,
    b.defender_name,
    b.result,
    b.created_at,
    b.notes,

    ao.power AS attacker_power,
    ao.squad AS attacker_squad,
    ao.losses AS attacker_losses,
    ao.injured AS attacker_injured,
    ao.lightly_injured AS attacker_lightly_injured,
    ao.residents AS attacker_residents,

    do_.power AS defender_power,
    do_.squad AS defender_squad,
    do_.losses AS defender_losses,
    do_.injured AS defender_injured,
    do_.lightly_injured AS defender_lightly_injured,
    do_.residents AS defender_residents,

    MAX(CASE WHEN tr.side='attacker' AND tr.troop_type='infantry' THEN tr.ratio END) AS attacker_infantry_ratio,
    MAX(CASE WHEN tr.side='attacker' AND tr.troop_type='infantry' THEN tr.was_present END) AS attacker_infantry_present,
    MAX(CASE WHEN tr.side='attacker' AND tr.troop_type='infantry' THEN tr.troop_level END) AS attacker_infantry_troop_level,
    MAX(CASE WHEN tr.side='attacker' AND tr.troop_type='infantry' THEN tr.tg_level END) AS attacker_infantry_tg_level,

    MAX(CASE WHEN tr.side='attacker' AND tr.troop_type='cavalry' THEN tr.ratio END) AS attacker_cavalry_ratio,
    MAX(CASE WHEN tr.side='attacker' AND tr.troop_type='cavalry' THEN tr.was_present END) AS attacker_cavalry_present,
    MAX(CASE WHEN tr.side='attacker' AND tr.troop_type='cavalry' THEN tr.troop_level END) AS attacker_cavalry_troop_level,
    MAX(CASE WHEN tr.side='attacker' AND tr.troop_type='cavalry' THEN tr.tg_level END) AS attacker_cavalry_tg_level,

    MAX(CASE WHEN tr.side='attacker' AND tr.troop_type='archer' THEN tr.ratio END) AS attacker_archer_ratio,
    MAX(CASE WHEN tr.side='attacker' AND tr.troop_type='archer' THEN tr.was_present END) AS attacker_archer_present,
    MAX(CASE WHEN tr.side='attacker' AND tr.troop_type='archer' THEN tr.troop_level END) AS attacker_archer_troop_level,
    MAX(CASE WHEN tr.side='attacker' AND tr.troop_type='archer' THEN tr.tg_level END) AS attacker_archer_tg_level,

    MAX(CASE WHEN tr.side='defender' AND tr.troop_type='infantry' THEN tr.ratio END) AS defender_infantry_ratio,
    MAX(CASE WHEN tr.side='defender' AND tr.troop_type='infantry' THEN tr.was_present END) AS defender_infantry_present,
    MAX(CASE WHEN tr.side='defender' AND tr.troop_type='infantry' THEN tr.troop_level END) AS defender_infantry_troop_level,
    MAX(CASE WHEN tr.side='defender' AND tr.troop_type='infantry' THEN tr.tg_level END) AS defender_infantry_tg_level,

    MAX(CASE WHEN tr.side='defender' AND tr.troop_type='cavalry' THEN tr.ratio END) AS defender_cavalry_ratio,
    MAX(CASE WHEN tr.side='defender' AND tr.troop_type='cavalry' THEN tr.was_present END) AS defender_cavalry_present,
    MAX(CASE WHEN tr.side='defender' AND tr.troop_type='cavalry' THEN tr.troop_level END) AS defender_cavalry_troop_level,
    MAX(CASE WHEN tr.side='defender' AND tr.troop_type='cavalry' THEN tr.tg_level END) AS defender_cavalry_tg_level,

    MAX(CASE WHEN tr.side='defender' AND tr.troop_type='archer' THEN tr.ratio END) AS defender_archer_ratio,
    MAX(CASE WHEN tr.side='defender' AND tr.troop_type='archer' THEN tr.was_present END) AS defender_archer_present,
    MAX(CASE WHEN tr.side='defender' AND tr.troop_type='archer' THEN tr.troop_level END) AS defender_archer_troop_level,
    MAX(CASE WHEN tr.side='defender' AND tr.troop_type='archer' THEN tr.tg_level END) AS defender_archer_tg_level
FROM battles b
LEFT JOIN battle_outcomes ao
    ON ao.battle_id=b.battle_id AND ao.side='attacker'
LEFT JOIN battle_outcomes do_
    ON do_.battle_id=b.battle_id AND do_.side='defender'
LEFT JOIN troop_ratios tr
    ON tr.battle_id=b.battle_id
GROUP BY
    b.battle_id, b.battle_key, b.battle_timestamp,
    b.attacker_name, b.defender_name, b.result, b.created_at, b.notes,
    ao.power, ao.squad, ao.losses, ao.injured, ao.lightly_injured, ao.residents,
    do_.power, do_.squad, do_.losses, do_.injured, do_.lightly_injured, do_.residents;

CREATE VIEW IF NOT EXISTS vw_battle_troops AS
SELECT
    b.battle_id,
    b.battle_key,
    b.battle_timestamp,
    b.attacker_name,
    b.defender_name,
    b.result,
    tr.side,
    tr.troop_type,
    tr.ratio,
    tr.was_present,
    tr.troop_level,
    tr.tg_level,
    tr.confidence
FROM battles b
JOIN troop_ratios tr ON tr.battle_id=b.battle_id;

CREATE VIEW IF NOT EXISTS vw_battle_bonuses AS
SELECT
    b.battle_id,
    b.battle_key,
    b.battle_timestamp,
    b.attacker_name,
    b.defender_name,
    b.result,
    tb.side,
    tb.troop_type,
    tb.stat,
    tb.value,
    tb.confidence
FROM battles b
JOIN troop_bonuses tb ON tb.battle_id=b.battle_id;

CREATE VIEW IF NOT EXISTS vw_battle_heroes AS
SELECT
    b.battle_id,
    b.battle_key,
    b.battle_timestamp,
    b.attacker_name,
    b.defender_name,
    b.result,
    bh.side,
    bh.role,
    bh.slot,
    h.name AS hero_name,
    h.generation AS hero_generation,
    h.troop_type AS hero_troop_type,
    bh.join_value,
    bh.match_confidence,
    bh.ocr_confidence
FROM battles b
JOIN battle_heroes bh ON bh.battle_id=b.battle_id
JOIN heroes h ON h.hero_id=bh.hero_id;
