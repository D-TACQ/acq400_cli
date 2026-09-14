#!/usr/bin/env python3

"""
Steam AWG waveforms to UUTs
"""

from acq400_cli import ArgTypes, Collection, ArgParser, Ansi
import time

def main(args):
    print(args)
    uuts = Collection(args.uutnames)
    uuts.abort_awg()

    print(f"Configuring {uuts.names}")
    uuts.configure_awg(
        trigger=args.trigger,
        rgm=args.rgm,
        source='AWG',
        burstlen=args.burstlen,
        clock=args.clock,
        clock_div=args.clock_div,
    )

    print(f"Stream to AWG {uuts.names}")
    tasks = uuts.bg.stream_to_awg(waveforms=args.filepaths)

    try:
        nlines = 0
        while True:
            Ansi.move_up(nlines)
            for uutname, task in tasks.items():
                total = getattr(task.thread, 'status', {}).get('total_bytes', 0)
                print(f"> {uutname} {total / (1024 ** 2):.2f} MB{Ansi.CLEAR}")
            nlines = len(tasks)
            time.sleep(1)
    except KeyboardInterrupt:
        print("Interrupt")
        for task in tasks.values():
            task.stop()
        for task in tasks.values():
            task.join()


def get_parser():
    parser = ArgParser(description='Steam AWG waveforms to UUTs')
    parser.add_argument('--trigger', '--trg', default='EXT,RISING', type=ArgTypes.signal_triplet, help='AWG Trigger')
    parser.add_argument('--rgm', default='0,0,0', type=ArgTypes.rgm_triplet, help='RGM triplet')
    parser.add_argument('--burstlen', default=0, type=int, help='Burstlen value')
    parser.add_argument('--clock', '--clk', default=None, type=ArgTypes.clock_triplet, help='clk triplet')
    parser.add_argument('--clock_div', '--clkdiv', default=None, type=ArgTypes.signal_triplet, help='gpg clk triplet')

    parser.add_argument('uutnames_and_filepaths', nargs='+', action=ArgTypes.uutnames_and_filepaths, help="uut hostnames and waveforms")
    return parser

if __name__ == '__main__':
    main(get_parser().parse_args())
