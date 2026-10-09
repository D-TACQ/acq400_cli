#!/usr/bin/env python3

"""
Generate waveform datafile from wdef file or args
"""

from acq400_cli import ArgParser, ArgTypes, generate_timestamp
from acq400_cli.waveform import WDEF, Waveform, WaveformSpec
from matplotlib import pyplot as plt
from pathlib import Path
import os


def main(args):
    if args.wavedef:
        print(f"Reading wavedef from {args.wavedef}")
        specs = WDEF.from_file(args.wavedef)
    else:
        specs = [WaveformSpec.from_spec({
            key: value
            for key, value in {
                'chan': args.chan,
                'index': args.index,
                'wavelength': args.wavelength,
                'cycles': args.cycles,
                'truncate': args.truncate,
                'skip': args.skip,
                'sense': args.sense,
                'phase_offset': args.phase,
                'dc_offset': args.dc,
                'shape': args.shape,
                'scale': args.scale,
            }.items()
            if value is not None
        })]
    waveform = Waveform(args.length, args.nchan, args.data_size, specs)

    if args.save:
        if isinstance(args.save, str):
            label = args.save
        elif args.wavedef:
            label = Path(args.wavedef).stem
        else:
            label = generate_timestamp()
        filename = f"{label}.{waveform.sample_format.tag}.wdat"
        os.makedirs(args.root, exist_ok=True)
        savepath = os.path.join(args.root, filename)
        print(f"Waveform saved to {savepath}")
        waveform.save_to_file(savepath)

    if not args.no_plot:
        for chan in waveform.sample_format.channels:
            plt.plot(waveform[f"{chan}"], label=f"CH{chan}")
        plt.legend(loc="upper right")
        plt.show()

def get_parser():
    parser = ArgParser(description='Generate waveform bin file from wdef file')
    parser.add_argument('--nchan', required=True, type=int, help='Total Channels')
    parser.add_argument('--length', required=True, type=ArgTypes.int_with_unit, help='Channel length in samples')
    parser.add_argument('--data_size', required=True, type=ArgTypes.int_with_unit, help='Channel size in bytes')
    parser.add_argument('--wavedef', default=None, type=ArgTypes.filepath, help="Waveform def file")
    parser.add_argument('--save', nargs='?', const=True, default=False, help="Save waveform, optionally --save=label")
    parser.add_argument('--root', default="WAVEFORMS", type=str, help="Waveform save root dir")
    parser.add_argument('--no_plot', action='store_true', help="Don't plot waveform")

    parser.add_argument('--chan', default=None, help='Channels to write')
    parser.add_argument('--index', default=None, help='Sample index where the waveform is anchored')
    parser.add_argument('--wavelength', default=None, help='Samples per cycle')
    parser.add_argument('--cycles', default=None, help='Number of cycles')
    parser.add_argument('--truncate', default=None, help='Max samples to keep from the generated waveform')
    parser.add_argument('--skip', default=None, help='Samples to drop from the start of the generated waveform')
    parser.add_argument('--sense', default=None, help='RISING starts at index; FALLING ends at index')
    parser.add_argument('--phase', default=None, help='Phase offset in radians')
    parser.add_argument('--dc', default=None, help='Vertical offset as a fraction of full scale')
    parser.add_argument('--shape', default=None, help='Waveform type: SINE, SQUARE, RAMP, or DC')
    parser.add_argument('--scale', default=None, help='Amplitude as a fraction of full scale')


    return parser

if __name__ == '__main__':
    main(get_parser().parse_args())