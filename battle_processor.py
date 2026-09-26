"""Assemble one battle from the three validated screenshot domains and persist atomically."""
from __future__ import annotations
from contextlib import closing
from pathlib import Path
import db
from battle_heroes import analyze_battle_heroes
from outcome_reader import extract_battle_outcome
from percent_reader import extract_ratios_bonuses, TROOP_ORDER

SIDES=('attacker','defender')
STATS=('attack','defense','lethality','health')


def _slot_parts(slot: str):
    # attacker.hero1 / defender.hero3
    side, hero = slot.split('.')
    return side, int(hero.removeprefix('hero'))


def normalize_ratios(extracted):
    """Return all 6 side/troop rows; absent screenshot entries become zero."""
    found={}
    rows=[]
    for key,item in extracted.items():
        side=key.split('.',1)[0]
        found[(side,item['troop_type'])]=item['reading']
    for side in SIDES:
        for troop in TROOP_ORDER:
            reading=found.get((side,troop))
            rows.append((side,troop,reading.value if reading else 0.0,1 if reading else 0,reading.confidence if reading else None))
    return rows


def extract_complete_battle(outcome_image, heroes_image, ratios_bonuses_image):
    outcome=extract_battle_outcome(outcome_image)
    heroes=analyze_battle_heroes(heroes_image)
    rb=extract_ratios_bonuses(ratios_bonuses_image)
    unknown=[slot for slot,r in heroes.items() if not r.accepted]
    if unknown:
        raise ValueError('Unrecognized lead hero(s): '+', '.join(unknown))
    return {'outcome':outcome,'heroes':heroes,'ratios':normalize_ratios(rb['ratios']),'bonuses':rb['bonuses']}


def process_battle(outcome_image, heroes_image, ratios_bonuses_image, db_path=None, notes=None):
    data=extract_complete_battle(outcome_image,heroes_image,ratios_bonuses_image)
    db.init_db(db_path); db.seed_heroes(db_path)
    with closing(db.connect(db_path)) as conn:
        try:
            conn.execute('BEGIN IMMEDIATE')
            next_id=conn.execute('SELECT COALESCE(MAX(battle_id),0)+1 FROM battles').fetchone()[0]
            battle_key=f'B{next_id:06d}'
            cur=conn.execute('''INSERT INTO battles(battle_id,battle_key,outcome_image,heroes_image,ratios_bonuses_image,notes)
                VALUES (?,?,?,?,?,?)''',(next_id,battle_key,str(outcome_image),str(heroes_image),str(ratios_bonuses_image),notes))
            battle_id=cur.lastrowid or next_id
            for side in SIDES:
                vals=[data['outcome'][f'{side}.{f}'].value for f in ('power','squad','losses','injured','lightly_injured','residents')]
                conn.execute('''INSERT INTO battle_outcomes
                    (battle_id,side,power,squad,losses,injured,lightly_injured,residents)
                    VALUES (?,?,?,?,?,?,?,?)''',(battle_id,side,*vals))
            for side,troop,ratio,present,conf in data['ratios']:
                conn.execute('INSERT INTO troop_ratios VALUES (?,?,?,?,?,?)',(battle_id,side,troop,ratio,present,conf))
            for key,r in data['bonuses'].items():
                side,rest=key.split('.',1); troop,stat=rest.rsplit('_',1)
                conn.execute('INSERT INTO troop_bonuses VALUES (?,?,?,?,?,?)',(battle_id,side,troop,stat,r.value,r.confidence))
            hero_ids={name:hid for hid,name in conn.execute('SELECT hero_id,name FROM heroes')}
            for slot,r in data['heroes'].items():
                side,n=_slot_parts(slot)
                conn.execute('''INSERT INTO battle_heroes
                    (battle_id,side,role,slot,hero_id,join_value,match_confidence,ocr_confidence)
                    VALUES (?,?,?,?,?,?,?,?)''',(battle_id,side,'lead',n,hero_ids[r.name],r.join_value,r.match_confidence,r.value_confidence))
            conn.commit()
            return battle_key
        except BaseException:
            conn.rollback()
            raise


def load_battle(battle_key,db_path=None):
    with closing(db.connect(db_path)) as conn:
        row=conn.execute('SELECT battle_id,battle_key,created_at,notes FROM battles WHERE battle_key=?',(battle_key,)).fetchone()
        if not row: raise KeyError(f'Battle not found: {battle_key}')
        bid=row[0]
        return {
            'battle':row,
            'outcomes':conn.execute('SELECT side,power,squad,losses,injured,lightly_injured,residents FROM battle_outcomes WHERE battle_id=? ORDER BY side',(bid,)).fetchall(),
            'ratios':conn.execute('SELECT side,troop_type,ratio,was_present FROM troop_ratios WHERE battle_id=? ORDER BY side, CASE troop_type WHEN "infantry" THEN 1 WHEN "cavalry" THEN 2 ELSE 3 END',(bid,)).fetchall(),
            'bonuses':conn.execute('SELECT side,troop_type,stat,value FROM troop_bonuses WHERE battle_id=? ORDER BY side,troop_type,stat',(bid,)).fetchall(),
            'heroes':conn.execute('''SELECT bh.side,bh.role,bh.slot,h.name,bh.join_value FROM battle_heroes bh JOIN heroes h USING(hero_id)
                WHERE bh.battle_id=? ORDER BY bh.side,bh.role,bh.slot''',(bid,)).fetchall(),
        }


def add_joiner(battle_key, side, hero_name, db_path=None):
    """Manually attach a joining hero to an existing battle."""
    if side not in SIDES:
        raise ValueError(f'Invalid side: {side}')
    db.init_db(db_path); db.seed_heroes(db_path)
    with closing(db.connect(db_path)) as conn:
        try:
            conn.execute('BEGIN IMMEDIATE')
            battle=conn.execute('SELECT battle_id FROM battles WHERE battle_key=?',(battle_key,)).fetchone()
            if not battle:
                raise KeyError(f'Battle not found: {battle_key}')
            hero=conn.execute('SELECT hero_id,name FROM heroes WHERE name=? COLLATE NOCASE',(hero_name,)).fetchone()
            if not hero:
                raise ValueError(f'Unknown hero: {hero_name}')
            bid=battle[0]
            duplicate=conn.execute('''SELECT 1 FROM battle_heroes WHERE battle_id=? AND side=? AND role='joiner' AND hero_id=?''',(bid,side,hero[0])).fetchone()
            if duplicate:
                raise ValueError(f'{hero[1]} is already a {side} joiner for {battle_key}')
            slot=conn.execute("SELECT COALESCE(MAX(slot),0)+1 FROM battle_heroes WHERE battle_id=? AND side=? AND role='joiner'",(bid,side)).fetchone()[0]
            conn.execute('''INSERT INTO battle_heroes
                (battle_id,side,role,slot,hero_id,join_value,match_confidence,ocr_confidence)
                VALUES (?,?,?,?,?,NULL,NULL,NULL)''',(bid,side,'joiner',slot,hero[0]))
            conn.commit()
            return slot,hero[1]
        except BaseException:
            conn.rollback(); raise


def remove_joiner(battle_key, side, slot, db_path=None):
    """Remove one manually entered joiner; lead heroes can never be removed here."""
    if side not in SIDES:
        raise ValueError(f'Invalid side: {side}')
    with closing(db.connect(db_path)) as conn:
        try:
            conn.execute('BEGIN IMMEDIATE')
            battle=conn.execute('SELECT battle_id FROM battles WHERE battle_key=?',(battle_key,)).fetchone()
            if not battle:
                raise KeyError(f'Battle not found: {battle_key}')
            row=conn.execute('''SELECT h.name FROM battle_heroes bh JOIN heroes h USING(hero_id)
                WHERE bh.battle_id=? AND bh.side=? AND bh.role='joiner' AND bh.slot=?''',(battle[0],side,slot)).fetchone()
            if not row:
                raise KeyError(f'Joiner not found: {battle_key} {side}.joiner{slot}')
            conn.execute("DELETE FROM battle_heroes WHERE battle_id=? AND side=? AND role='joiner' AND slot=?",(battle[0],side,slot))
            conn.commit(); return row[0]
        except BaseException:
            conn.rollback(); raise
