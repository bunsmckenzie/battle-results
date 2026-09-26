import argparse
import db


def main():
    parser = argparse.ArgumentParser()
    sub = parser.add_subparsers(dest='command', required=True)
    sub.add_parser('init-db')
    sub.add_parser('seed-heroes')
    args = parser.parse_args()
    if args.command == 'init-db':
        db.init_db()
        print('Database initialized: battle_data.sqlite3')
    elif args.command == 'seed-heroes':
        db.seed_heroes()
        print('Hero reference catalog loaded.')


if __name__ == '__main__':
    main()
