import argparse
import db
from layout import LayoutCatalog, write_debug_crops
from hero_matcher import match_battle_heroes
from hero_values import extract_battle_join_values
from battle_heroes import analyze_battle_heroes
from outcome_reader import extract_battle_outcome
from percent_reader import extract_ratios_bonuses
from battle_processor import process_battle, load_battle, add_joiner, remove_joiner


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
    rb = sub.add_parser('read-ratios-bonuses')
    rb.add_argument('--image', required=True)
    combined = sub.add_parser('analyze-heroes')
    combined.add_argument('--image', required=True)
    process = sub.add_parser('process-battle')
    process.add_argument('--outcome', required=True)
    process.add_argument('--heroes', required=True)
    process.add_argument('--ratios-bonuses', required=True)
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
    args = parser.parse_args()
    if args.command == 'init-db':
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
    elif args.command == 'read-ratios-bonuses':
        result = extract_ratios_bonuses(args.image)
        for slot, item in result['ratios'].items():
            r=item['reading']; print(f"{slot}: {item['troop_type']} {r.value:.2f}% confidence={r.confidence:.3f}")
        for field, r in result['bonuses'].items():
            print(f'{field}: +{r.value:.1f}% confidence={r.confidence:.3f}')
    elif args.command == 'analyze-heroes':
        for slot, reading in analyze_battle_heroes(args.image).items():
            label = reading.name if reading.accepted else 'UNKNOWN'
            print(f'{slot}: {label} join_value={reading.join_value} match_confidence={reading.match_confidence:.3f} value_confidence={reading.value_confidence:.3f}')
    elif args.command == 'process-battle':
        key=process_battle(args.outcome,args.heroes,args.ratios_bonuses,notes=args.notes)
        print(f'Battle saved: {key}')
    elif args.command == 'add-joiner':
        slot,name=add_joiner(args.battle_key,args.side,args.hero)
        print(f'Joiner added: {args.battle_key} {args.side}.joiner{slot}: {name}')
    elif args.command == 'remove-joiner':
        name=remove_joiner(args.battle_key,args.side,args.slot)
        print(f'Joiner removed: {args.battle_key} {args.side}.joiner{args.slot}: {name}')
    elif args.command == 'show-battle':
        b=load_battle(args.battle_key)
        print(f'Battle {b["battle"][1]} created={b["battle"][2]}')
        print('OUTCOMES')
        for r in b['outcomes']: print('  '+ ' | '.join(map(str,r)))
        print('RATIOS')
        for side,troop,ratio,present in b['ratios']: print(f'  {side}.{troop}: {ratio:.2f}% present={present}')
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
