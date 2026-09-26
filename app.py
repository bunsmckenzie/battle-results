import argparse
import db
from layout import LayoutCatalog, write_debug_crops


def main():
    parser = argparse.ArgumentParser()
    sub = parser.add_subparsers(dest='command', required=True)
    sub.add_parser('init-db')
    sub.add_parser('seed-heroes')
    debug = sub.add_parser('debug-layout')
    debug.add_argument('--type', required=True, choices=LayoutCatalog.load().names())
    debug.add_argument('--image', required=True)
    debug.add_argument('--out', default='debug_crops')
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


if __name__ == '__main__':
    main()
