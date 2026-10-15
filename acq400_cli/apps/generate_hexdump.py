#!/usr/bin/env python3

"""
Generate hexdump command for UUTs
"""

from acq400_cli import Collection, ArgParser

def main(args):
    uuts = Collection(args.uutnames)
    for uut in uuts:
        print(f"[{uut.hostname}](stream): {uut.stream_sample_format.gen_hexdump_cmd(args.as_width)}")
        print(f"[{uut.hostname}](transient): {uut.transient_sample_format.gen_hexdump_cmd(args.as_width)}")

def get_parser():
    parser = ArgParser(description='Generate hexdump command for UUTs')
    parser.add_argument('--as_width', default=None, choices=(2, 4), type=int, help='Force output channel width')
    parser.add_argument('uutnames', nargs='+', help="uut hostnames")
    return parser

if __name__ == '__main__':
    main(get_parser().parse_args())