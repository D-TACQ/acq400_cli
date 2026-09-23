#!/usr/bin/env python3

"""
Upload AWG segment waveforms to UUTs
"""

import time
from acq400_cli import ArgTypes, Collection, ArgParser, AWG_SEG_MODE

def main(args):
    uuts = Collection(args.uutnames)

    print(f"Configuring {uuts.names}")
    uuts.configure_awg(
        trigger=args.trigger,
        rgm='0,0,0',
        source='AWG',
        burstlen=0,
        clock=args.clock,
        clock_div=args.clock_div,
    )

    for idx, waveform in enumerate(args.filepaths):
        segment = chr(ord('A') + idx)
        print(f"Upload {waveform} to segment {segment} {uuts.names}")
        uuts.load_awg_seg(
            waveform=waveform,
            segment=segment,
            mode=AWG_SEG_MODE['REARM'],
            repeat=0,
        )

    pattern = args.pattern if args.pattern else ''.join([chr(ord('A') + i) for i in range(len(args.filepaths))])

    print(f"Sending pattern '{pattern}'")
    tasks = uuts.bg.feed_awg_segment_pattern(pattern)
    try:
        while True: time.sleep(1)
    except KeyboardInterrupt:
        print("Interrupt")
        for task in tasks.values():
            task.stop()
        for task in tasks.values():
            task.join()

def get_parser():
    parser = ArgParser(description='Upload AWG waveforms to UUTs')
    parser.add_argument('--trigger', '--trg', default='SOFT,RISING', type=ArgTypes.signal_triplet, help='AWG Trigger')
    parser.add_argument('--rgm', default='0,0,0', type=ArgTypes.rgm_triplet, help='RGM triplet')
    parser.add_argument('--burstlen', default=0, type=int, help='Burstlen value')
    parser.add_argument('--clock', '--clk', default=None, type=ArgTypes.clock_triplet, help='clk triplet')
    parser.add_argument('--clock_div', '--clkdiv', default=None, type=ArgTypes.signal_triplet, help='gpg clk triplet')
    parser.add_argument('--pattern', default=None, type=str.upper, help='AWG Segment play pattern')

    parser.add_argument('uutnames_and_filepaths', nargs='+', action=ArgTypes.uutnames_and_filepaths, help="uut hostnames and waveforms")
    return parser

if __name__ == '__main__':
    main(get_parser().parse_args())
 