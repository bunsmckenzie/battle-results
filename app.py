import argparse
import db
from layout import LayoutCatalog, write_debug_crops
from hero_matcher import match_battle_heroes
from hero_values import extract_battle_join_values
from battle_heroes import analyze_battle_heroes


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
    combined = sub.add_parser('analyze-heroes')
    combined.add_argument('--image', required=True)
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
    elif args.command == 'analyze-heroes':
        for slot, reading in analyze_battle_heroes(args.image).items():
            label = reading.name if reading.accepted else 'UNKNOWN'
            print(f'{slot}: {label} join_value={reading.join_value} match_confidence={reading.match_confidence:.3f} value_confidence={reading.value_confidence:.3f}')
    elif args.command == 'match-heroes':
        for slot, match in match_battle_heroes(args.image).items():
            label = match.name if match.accepted else 'UNKNOWN'
            candidates = ', '.join(f'{c.name}:{c.good_matches}' for c in match.candidates)
            print(f'{slot}: {label} confidence={match.confidence:.3f} matches={match.good_matches} candidates=[{candidates}]')


if __name__ == '__main__':
    main()
