"""Stitch PNG frames into a GIF.

    python media/make_gif.py <frame_dir> <out.gif>
"""
from __future__ import print_function

import glob
import os
import sys

from PIL import Image


def main(argv=None):
    argv = argv if argv is not None else sys.argv[1:]
    if len(argv) < 2:
        print(__doc__)
        print('usage: python media/make_gif.py <frame_dir> <out.gif> [duration_ms]')
        return 2
    frame_dir, out_path = argv[0], argv[1]
    duration = int(argv[2]) if len(argv) > 2 else int(os.environ.get('FLD_GIF_DURATION', '100'))
    paths = sorted(glob.glob(os.path.join(frame_dir, 'frame_*.png')))
    if not paths:
        print('no frames in %s' % frame_dir)
        return 1
    frames = [Image.open(p).convert('RGB') for p in paths]
    out_dir = os.path.dirname(os.path.abspath(out_path))
    if out_dir and not os.path.isdir(out_dir):
        os.makedirs(out_dir)
    frames[0].save(
        out_path,
        save_all=True,
        append_images=frames[1:],
        duration=duration,
        loop=0,
        disposal=2,
    )
    print('wrote %s (%d frames, %d ms/frame, disposal=2)' % (out_path, len(frames), duration))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
