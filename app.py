import argparse
import db
from layout import LayoutCatalog, write_debug_crops
from hero_matcher import match_battle_heroes
from hero_values import extract_battle_join_values
from battle_heroes import analyze_battle_heroes
from outcome_reader import extract_battle_outcome
from percent_reader import extract_ratios_bonuses
from battle_processor import process_battle, load_battle, add_joiner, remove_joiner, DuplicateBattleError
from screenshot_classifier import classify_image, classify_folder
from folder_router import resolve_battle_images
from batch_ingestion import preflight_batch, ingest_batch
from battle_metadata import extract_battle_metadata
from reporting_views import preview_view, REPORTING_VIEWS


def main():
    parser = argparse.ArgumentParser()
    sub = parser.add_subparsers(dest='command', required=True)
    sub.add_parser('init-db')
    sub.add_parser('seed-heroes')
    debug = sub.add_parser('debug-layout')
    debug.add_argument('--type', required=True, choices=LayoutCatalog.load().names())
    debug.add_argument('--image', required=True)
    debug.add_argument('--out', default='debug_crops')
    heroes = sub.add_parser('match-heroes')
    heroes.add_argument('--image', required=True)
    values = sub.add_parser('read-hero-values')
    values.add_argument('--image', required=True)
    outcome = sub.add_parser('read-outcome')
    outcome.add_argument('--image', required=True)
    metadata = sub.add_parser('read-battle-metadata')
    metadata.add_argument('--image', required=True)
    rb = sub.add_parser('read-ratios-bonuses')
    rb.add_argument('--image', required=True)
    combined = sub.add_parser('analyze-heroes')
    combined.add_argument('--image', required=True)
    process = sub.add_parser('process-battle')
    source = process.add_mutually_exclusive_group(required=True)
    source.add_argument('--folder')
    source.add_argument('--outcome')
    process.add_argument('--heroes')
    process.add_argument('--ratios-bonuses')
    process.add_argument('--notes')
    show = sub.add_parser('show-battle')
    show.add_argument('battle_key')
    addj = sub.add_parser('add-joiner')
    addj.add_argument('battle_key')
    addj.add_argument('--side', required=True, choices=('attacker','defender'))
    addj.add_argument('--hero', required=True)
    remj = sub.add_parser('remove-joiner')
    remj.add_argument('battle_key')
    remj.add_argument('--side', required=True, choices=('attacker','defender'))
    remj.add_argument('--slot', required=True, type=int)
    ci=sub.add_parser('classify-image'); ci.add_argument('--image',required=True)
    cf=sub.add_parser('classify-folder'); cf.add_argument('--folder',required=True)
    batch=sub.add_parser('batch-ingest')
    batch.add_argument('--parent', required=True)
    batch.add_argument('--dry-run', action='store_true')
    preview=sub.add_parser('preview-view')
    preview.add_argument('--view', required=True, choices=tuple(REPORTING_VIEWS))
    preview.add_argument('--limit', type=int, default=10)
    args = parser.parse_args()
    if args.command == 'preview-view':
        view, columns, rows = preview_view(args.view, args.limit)
        print(f'{view} rows={len(rows)}')
        print(' | '.join(columns))
        for row in rows:
            print(' | '.join('NULL' if value is None else str(value) for value in row))
    elif args.command == 'batch-ingest':
        items = preflight_batch(args.parent) if args.dry_run else ingest_batch(args.parent)
        for item in items:
            if item.status == 'READY':
                print(f'{item.folder}: READY')
            elif item.status == 'SAVED':
                print(f'{item.folder}: SAVED {item.battle_key}')
            elif item.status == 'DUPLICATE':
                target = item.battle_key or item.duplicate_of or 'another folder in this batch'
                print(f'{item.folder}: DUPLICATE -> {target}')
            else:
                print(f'{item.folder}: {item.status} - {item.error}')
        ready_saved = sum(i.status in ('READY','SAVED') for i in items)
        duplicates = sum(i.status == 'DUPLICATE' for i in items)
        failed = len(items) - ready_saved - duplicates
        label = 'ready' if args.dry_run else 'saved'
        print(f'Batch summary: {label}={ready_saved} duplicates={duplicates} failed={failed} total={len(items)}')
    elif args.command == 'classify-image':
        r=classify_image(args.image); print(f'{r.image_type} confidence={r.confidence:.3f}')
    elif args.command == 'classify-folder':
        for path,r in classify_folder(args.folder).items(): print(f'{path}: {r.image_type} confidence={r.confidence:.3f}')
    elif args.command == 'init-db':
        db.init_db()
        print('Database initialized: battle_data.sqlite3')
    elif args.command == 'seed-heroes':
        db.seed_heroes()
        print('Hero reference catalog loaded.')
    elif args.command == 'debug-layout':
        paths = write_debug_crops(args.image, args.type, args.out)
        print(f'Wrote {len(paths)} debug crops to {args.out}')
    elif args.command == 'read-hero-values':
        for slot, reading in extract_battle_join_values(args.image).items():
            print(f'{slot}: {reading.value} confidence={reading.confidence:.3f} raw={reading.raw_text!r}')
    elif args.command == 'read-outcome':
        for field, reading in extract_battle_outcome(args.image).items():
            print(f'{field}: {reading.value:,} confidence={reading.confidence:.3f}')
    elif args.command == 'read-battle-metadata':
        m=extract_battle_metadata(args.image)
        print(f'attacker_name: {m.attacker_name}')
        print(f'defender_name: {m.defender_name}')
        print(f'result: {m.result}')
    elif args.command == 'read-ratios-bonuses':
        result = extract_ratios_bonuses(args.image)
        for slot, item in result['ratios'].items():
            r=item['reading']; tl=item['troop_level']; tg=item['tg_level']; print(f"{slot}: {item['troop_type']} {r.value:.2f}% troop_level={tl.value:.1f} tg_level={tg.value} confidence={r.confidence:.3f}")
        for field, r in result['bonuses'].items():
            print(f'{field}: +{r.value:.1f}% confidence={r.confidence:.3f}')
    elif args.command == 'analyze-heroes':
        for slot, reading in analyze_battle_heroes(args.image).items():
            label = reading.name if reading.accepted else 'UNKNOWN'
            print(f'{slot}: {label} join_value={reading.join_value} match_confidence={reading.match_confidence:.3f} value_confidence={reading.value_confidence:.3f}')
    elif args.command == 'process-battle':
        if args.folder:
            images = resolve_battle_images(args.folder)
            outcome_image = images['outcome']
            heroes_image = images['heroes']
            ratios_bonuses_image = images['ratios_bonuses']
            print(f'Auto-routed outcome: {outcome_image}')
            print(f'Auto-routed heroes: {heroes_image}')
            print(f'Auto-routed ratios_bonuses: {ratios_bonuses_image}')
        else:
            if not args.heroes or not args.ratios_bonuses:
                parser.error('explicit mode requires --outcome, --heroes, and --ratios-bonuses')
            outcome_image = args.outcome
            heroes_image = args.heroes
            ratios_bonuses_image = args.ratios_bonuses
        try:
            key=process_battle(outcome_image,heroes_image,ratios_bonuses_image,notes=args.notes)
            print(f'Battle saved: {key}')
        except DuplicateBattleError as exc:
            print(f'Battle duplicate: {exc.battle_key} identity={exc.identity}')
    elif args.command == 'add-joiner':
        slot,name=add_joiner(args.battle_key,args.side,args.hero)
        print(f'Joiner added: {args.battle_key} {args.side}.joiner{slot}: {name}')
    elif args.command == 'remove-joiner':
        name=remove_joiner(args.battle_key,args.side,args.slot)
        print(f'Joiner removed: {args.battle_key} {args.side}.joiner{args.slot}: {name}')
    elif args.command == 'show-battle':
        b=load_battle(args.battle_key)
        print(f'Battle {b["battle"][1]} created={b["battle"][2]}')
        if b['battle'][7]:
            print(f'IDENTITY timestamp={b["battle"][4]} x={b["battle"][5]} y={b["battle"][6]} key={b["battle"][7]}')
        else:
            print('IDENTITY unavailable (legacy cropped Outcome image)')
        if b['battle'][8] or b['battle'][9] or b['battle'][10]:
            print(f'METADATA result={b["battle"][10]} attacker={b["battle"][8]} defender={b["battle"][9]}')
        else:
            print('METADATA unavailable (legacy battle; reprocess to populate)')
        print('OUTCOMES')
        for r in b['outcomes']: print('  '+ ' | '.join(map(str,r)))
        print('RATIOS')
        for side,troop,ratio,present,troop_level,tg_level in b['ratios']:
            levels = f' troop_level={troop_level:.1f} tg_level={tg_level}' if present else ' troop_level=NULL tg_level=NULL'
            print(f'  {side}.{troop}: {ratio:.2f}% present={present}{levels}')
        print('BONUSES')
        for side,troop,stat,value in b['bonuses']: print(f'  {side}.{troop}_{stat}: +{value:.1f}%')
        print('HEROES')
        for side,role,slot,name,value in b['heroes']:
            suffix = f' join_value={value}' if role == 'lead' else ''
            print(f'  {side}.{role}{slot}: {name}{suffix}')
    elif args.command == 'match-heroes':
        for slot, match in match_battle_heroes(args.image).items():
            label = match.name if match.accepted else 'UNKNOWN'
            candidates = ', '.join(f'{c.name}:{c.good_matches}' for c in match.candidates)
            print(f'{slot}: {label} confidence={match.confidence:.3f} matches={match.good_matches} candidates=[{candidates}]')


if __name__ == '__main__':
    main()
