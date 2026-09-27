"""Assemble one battle from the three validated screenshot domains and persist atomically."""
from __future__ import annotations
from contextlib import closing
from pathlib import Path
import db
from battle_heroes import analyze_battle_heroes
from outcome_reader import extract_battle_outcome
from percent_reader import extract_ratios_bonuses, TROOP_ORDER
from battle_identity import extract_battle_identity, BattleIdentity
from battle_metadata import extract_battle_metadata

SIDES=('attacker','defender')
STATS=('attack','defense','lethality','health')


class DuplicateBattleError(ValueError):
    def __init__(self, battle_key: str, identity: str):
        self.battle_key = battle_key
        self.identity = identity
        super().__init__(f'Duplicate battle {identity}; already stored as {battle_key}')


def _database_path(db_path=None):
    return Path(db_path) if db_path is not None else db.DB_PATH


def find_duplicate_battle(identity: BattleIdentity | None, db_path=None):
    """Return existing battle_key for identity without creating/upgrading a DB."""
    if identity is None:
        return None
    path = _database_path(db_path)
    if not path.exists():
        return None
    with closing(db.connect(path)) as conn:
        columns={row[1] for row in conn.execute('PRAGMA table_info(battles)')}
        if 'battle_identity' in columns:
            row=conn.execute('SELECT battle_key FROM battles WHERE battle_identity=?',(identity.key,)).fetchone()
            if row:
                return row[0]
            legacy=conn.execute('SELECT battle_key,outcome_image FROM battles WHERE battle_identity IS NULL').fetchall()
        else:
            # Step 9.1 database: compare against stored Outcome paths in memory without modifying the DB.
            legacy=conn.execute('SELECT battle_key,outcome_image FROM battles').fetchall()
        for battle_key,outcome_image in legacy:
            if not outcome_image:
                continue
            try:
                old_identity=extract_battle_identity(outcome_image)
            except (OSError, ValueError):
                continue
            if old_identity is not None and old_identity.key == identity.key:
                return battle_key
        return None


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
        found[(side,item['troop_type'])]=item
    for side in SIDES:
        for troop in TROOP_ORDER:
            item=found.get((side,troop))
            reading=item['reading'] if item else None
            rows.append((side,troop,reading.value if reading else 0.0,1 if item else 0,reading.confidence if reading else None,
                         item['troop_level'].value if item else None,item['tg_level'].value if item else None))
    return rows


def extract_complete_battle(outcome_image, heroes_image, ratios_bonuses_image):
    identity=extract_battle_identity(outcome_image)
    metadata=extract_battle_metadata(outcome_image)
    outcome=extract_battle_outcome(outcome_image)
    heroes=analyze_battle_heroes(heroes_image)
    rb=extract_ratios_bonuses(ratios_bonuses_image)
    unknown=[slot for slot,r in heroes.items() if not r.accepted]
    if unknown:
        raise ValueError('Unrecognized lead hero(s): '+', '.join(unknown))
    return {'identity':identity,'metadata':metadata,'outcome':outcome,'heroes':heroes,'ratios':normalize_ratios(rb['ratios']),'bonuses':rb['bonuses']}


def process_battle(outcome_image, heroes_image, ratios_bonuses_image, db_path=None, notes=None):
    data=extract_complete_battle(outcome_image,heroes_image,ratios_bonuses_image)
    db.init_db(db_path); db.seed_heroes(db_path)
    legacy_duplicate=find_duplicate_battle(data['identity'], db_path=db_path)
    if legacy_duplicate and data['identity'] is not None:
        raise DuplicateBattleError(legacy_duplicate, data['identity'].key)
    with closing(db.connect(db_path)) as conn:
        try:
            conn.execute('BEGIN IMMEDIATE')
            identity=data['identity']
            if identity is not None:
                duplicate=conn.execute('SELECT battle_key FROM battles WHERE battle_identity=?',(identity.key,)).fetchone()
                if duplicate:
                    raise DuplicateBattleError(duplicate[0], identity.key)
            next_id=conn.execute('SELECT COALESCE(MAX(battle_id),0)+1 FROM battles').fetchone()[0]
            battle_key=f'B{next_id:06d}'
            cur=conn.execute('''INSERT INTO battles(
                    battle_id,battle_key,outcome_image,heroes_image,ratios_bonuses_image,notes,
                    battle_timestamp,coord_x,coord_y,battle_identity,attacker_name,defender_name,result)
                VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)''',(
                    next_id,battle_key,str(outcome_image),str(heroes_image),str(ratios_bonuses_image),notes,
                    identity.battle_timestamp if identity else None,
                    identity.coord_x if identity else None,
                    identity.coord_y if identity else None,
                    identity.key if identity else None,
                    data['metadata'].attacker_name,data['metadata'].defender_name,data['metadata'].result))
            battle_id=cur.lastrowid or next_id
            for side in SIDES:
                vals=[data['outcome'][f'{side}.{f}'].value for f in ('power','squad','losses','injured','lightly_injured','residents')]
                conn.execute('''INSERT INTO battle_outcomes
                    (battle_id,side,power,squad,losses,injured,lightly_injured,residents)
                    VALUES (?,?,?,?,?,?,?,?)''',(battle_id,side,*vals))
            for side,troop,ratio,present,conf,troop_level,tg_level in data['ratios']:
                conn.execute('''INSERT INTO troop_ratios
                    (battle_id,side,troop_type,ratio,was_present,confidence,troop_level,tg_level) VALUES (?,?,?,?,?,?,?,?)''',
                    (battle_id,side,troop,ratio,present,conf,troop_level,tg_level))
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
        row=conn.execute('''SELECT battle_id,battle_key,created_at,notes,battle_timestamp,coord_x,coord_y,battle_identity,attacker_name,defender_name,result
            FROM battles WHERE battle_key=?''',(battle_key,)).fetchone()
        if not row: raise KeyError(f'Battle not found: {battle_key}')
        bid=row[0]
        return {
            'battle':row,
            'outcomes':conn.execute('SELECT side,power,squad,losses,injured,lightly_injured,residents FROM battle_outcomes WHERE battle_id=? ORDER BY side',(bid,)).fetchall(),
            'ratios':conn.execute('SELECT side,troop_type,ratio,was_present,troop_level,tg_level FROM troop_ratios WHERE battle_id=? ORDER BY side, CASE troop_type WHEN "infantry" THEN 1 WHEN "cavalry" THEN 2 ELSE 3 END',(bid,)).fetchall(),
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
