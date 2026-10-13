#!/usr/bin/env python3

"""
Upload AWG waveforms to UUTs
"""

from acq400_cli import ArgTypes, Collection, ArgParser, AWG_MODE

def main(args):
    uuts = Collection(args.uutnames)
    uuts.abort_awg(timeout=10)

    print(f"Configuring {uuts.names}")
    uuts.configure_awg(
        trigger=args.trigger,
        rgm=args.rgm,
        source='AWG',
        burstlen=args.burstlen,
        clock=args.clock,
        clock_div=args.clock_div,
    )

    for idx, waveform in enumerate(args.filepaths):
        print(f"Upload {waveform} to {uuts.names}")
        uuts.load_awg(
            waveform=waveform,
            mode=args.mode,
            repeat=0,
            prepend=args.prepend0
        )
        if idx < len(args.filepaths) - 1:
            print(f"Wait for AWG IDLE on {uuts.names}")
            uuts.wait_for_awg_idle()


def get_parser():
    parser = ArgParser(description='Upload AWG waveforms to UUTs')
    parser.add_argument('--trigger', '--trg', default='SOFT,RISING', type=ArgTypes.signal_triplet, help='AWG Trigger')
    parser.add_argument('--rgm', default='0,0,0', type=ArgTypes.rgm_triplet, help='RGM triplet')
    parser.add_argument('--burstlen', default=0, type=int, help='Burstlen value')
    parser.add_argument('--clock', '--clk', default=None, type=ArgTypes.clock_triplet, help='clk triplet')
    parser.add_argument('--clock_div', '--clkdiv', default=None, type=ArgTypes.signal_triplet, help='gpg clk triplet')
    parser.add_argument('--mode', default='ONCE', choices=list(AWG_MODE.__members__), type=str.upper, help='AWG mode')
    parser.add_argument('--prepend0', action='store_true', help='prepend empty sample to start of waveform')

    parser.add_argument('uutnames_and_filepaths', nargs='+', action=ArgTypes.uutnames_and_filepaths, help="uut hostnames and waveforms")
    return parser

if __name__ == '__main__':
    main(get_parser().parse_args())
 