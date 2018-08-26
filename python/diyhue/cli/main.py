"""
CLI main entry point
"""

import argparse

def get_parser():
    parser = argparse.ArgumentParser(description='diyHue CLI')
    subparsers = parser.add_subparsers(help='commands', dest='command')

    start_parser = subparsers.add_parser('start', help='Start diyHue')
    start_parser.set_defaults(func=cli_start)

    help_parser = subparsers.add_parser('help', help='Show help')

    return parser

def cli_start(args):
    from .start import start
    start(args)

def main():
    parser = get_parser()
    args = parser.parse_args()
    if args.command == 'help':
        parser.print_help()
    elif args.command == 'start':
        args.func(args)
    else:
        parser.print_help()