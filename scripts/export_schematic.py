"""Export block population as a Sponge v2 schematic; never edits viewer settings.

Runs the same worker request the viewer sends, with lighting and curve colors
off so FSTAR003 colors are the base palette. Kinds come from the proxy shapes,
which `_block_population.proxy_shapes` makes unambiguous.
"""
from pathlib import Path
import argparse
import gzip
import json
import struct
import sys
import tempfile
import time

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT/'python'), str(ROOT/'generators')]
import worker
from _block_population import CANDLE_COLORS

DATA_VERSION = 5023  # Minecraft Java 26.3
# One block per CANDLE_COLORS tint. Night tint is the game's job, not the palette's.
CANDLE_BLOCKS = ('minecraft:candle', 'minecraft:white_candle', 'minecraft:light_gray_candle',
                 'minecraft:white_candle', 'minecraft:light_gray_candle')
ROD_FACING = ('east', 'up', 'south')
FULL_BLOCK = 'minecraft:ochre_froglight[axis=y]'
CANDLE_WIDTHS = np.array([2., 4., 5., 6.]) / 16
CANDLE_HEIGHT, ROD_WIDTH = 6/16, 2/16
assert len(CANDLE_BLOCKS) == len(CANDLE_COLORS)


def viewer_request(cfg, script=None, seed=None):
    """Request equivalent to GeneratorPanel's, with RGB-only overrides."""
    generator = cfg['generator']
    script = script or generator['script']
    params = dict(generator.get('parameters', {}).get(script, {}), pop_lighting=0, pop_colors=0)
    blocks = bool(cfg.get('block_units', True))
    return dict(generator=script, count=generator.get('count', 100000),
                seed=generator['seed'] if seed is None else seed, params=params,
                world_units='blocks' if blocks else 'legacy', density_graph=blocks,
                density_field=generator.get('density_field', {}),
                legacy_display_scale=cfg.get('legacy_display_scale', 16.))


def read_stars(path):
    data = path.read_bytes()
    magic, count = struct.unpack('<8sQ', data[:16])
    if magic != b'FSTAR003':
        raise ValueError('Star output has no block shapes; Minecraft material proxies must be on')
    if count == 0:
        raise ValueError('Generation produced no blocks')
    records = np.frombuffer(data[16:], '<f4').reshape(count, 10)
    return records[:, :3], records[:, 3:6], records[:, 7:10]


def decode(shapes, colors):
    """Kind 0 candle, 1 rod, 2 full block; candle count 1-4; rod axis; candle tint."""
    close = lambda a, b: np.abs(a-b) < 1e-6
    full = close(shapes, 1.).all(axis=1)
    rod = (close(shapes, 1.).sum(axis=1) == 1) & (close(shapes, ROD_WIDTH).sum(axis=1) == 2)
    width = close(shapes[:, :1], CANDLE_WIDTHS[None])
    candle = close(shapes[:, 1], CANDLE_HEIGHT) & close(shapes[:, 0], shapes[:, 2]) & width.any(axis=1)
    if (~(full | rod | candle)).any():
        raise ValueError(f'{int((~(full | rod | candle)).sum())} records match no block proxy shape')
    tint = close(colors[:, None], CANDLE_COLORS.astype(np.float32)[None]).all(axis=2)
    if (candle & ~tint.any(axis=1)).any():
        raise ValueError('Candle colors are not base palette tints; lighting and curve colors must be off')
    kinds = np.where(candle, 0, np.where(rod, 1, 2)).astype(np.int8)
    return kinds, width.argmax(axis=1)+1, np.argmax(close(shapes, 1.), axis=1), tint.argmax(axis=1)


def block_states(kinds, counts, axes, tints):
    return [f'{CANDLE_BLOCKS[t]}[candles={n},lit=false,waterlogged=false]' if k == 0 else
            f'minecraft:end_rod[facing={ROD_FACING[a]}]' if k == 1 else FULL_BLOCK
            for k, n, a, t in zip(kinds, counts, axes, tints)]


def varints(values):
    values = np.asarray(values, dtype=np.uint32).ravel()
    lengths = 1 + sum((values >= 1 << 7*k).astype(np.int64) for k in range(1, 5))
    starts = np.r_[0, np.cumsum(lengths)[:-1]]
    out = np.empty(int(lengths.sum()), dtype=np.uint8)
    for k in range(5):
        mask = lengths > k
        more = np.where(lengths[mask] > k+1, 0x80, 0)
        out[starts[mask]+k] = ((values[mask] >> 7*k) & 0x7f) | more
    return out.tobytes()


SHORT, INT, BYTE_ARRAY, STRING, LIST, COMPOUND, INT_ARRAY = 2, 3, 7, 8, 9, 10, 11


def _name(text):
    data = text.encode('utf-8')
    return struct.pack('>H', len(data)) + data


def _payload(tag, value):
    if tag == SHORT:
        return struct.pack('>h', value)
    if tag == INT:
        return struct.pack('>i', value)
    if tag == BYTE_ARRAY:
        return struct.pack('>i', len(value)) + bytes(value)
    if tag == STRING:
        return _name(value)
    if tag == INT_ARRAY:
        return struct.pack('>i', len(value)) + np.asarray(value, '>i4').tobytes()
    if tag == LIST:
        item, items = value
        return struct.pack('>bi', item, len(items)) + b''.join(_payload(item, v) for v in items)
    if tag == COMPOUND:
        return b''.join(struct.pack('>b', t) + _name(k) + _payload(t, v) for k, (t, v) in value.items()) + b'\0'
    raise ValueError(f'Unsupported NBT tag {tag}')


def schematic(cells, states, name):
    """Gzipped Sponge v2 bytes; the minimum occupied cell becomes the origin."""
    low = cells.min(axis=0)
    size = cells.max(axis=0) - low + 1
    if (size > 32767).any():
        raise ValueError(f'Schematic size {size.tolist()} exceeds 32767 blocks')
    palette = {'minecraft:air': 0}
    indices = np.array([palette.setdefault(s, len(palette)) for s in states], dtype=np.uint32)
    width, height, length = map(int, size)
    data = np.zeros((height, length, width), dtype=np.uint32)  # index x + z*W + y*W*L
    x, y, z = (cells - low).T
    data[y, z, x] = indices
    root = {'Version': (INT, 2), 'DataVersion': (INT, DATA_VERSION),
            'Width': (SHORT, width), 'Height': (SHORT, height), 'Length': (SHORT, length),
            'Offset': (INT_ARRAY, [0, 0, 0]), 'PaletteMax': (INT, len(palette)),
            'Palette': (COMPOUND, {s: (INT, i) for s, i in palette.items()}),
            'BlockData': (BYTE_ARRAY, varints(data)), 'BlockEntities': (LIST, (COMPOUND, [])),
            'Metadata': (COMPOUND, {'Name': (STRING, name), 'Author': (STRING, 'filaments')})}
    return gzip.compress(b'\x0a' + _name('Schematic') + _payload(COMPOUND, root), mtime=0), low, size


def generate_blocks(request):
    with tempfile.TemporaryDirectory() as directory:
        output = Path(directory)/'points.bin'
        response = worker.generate_request(request, ROOT/'generators', output)
        response.pop('catalog', None)
        if not response.get('ok'):
            raise RuntimeError(response.get('error'))
        if not response.get('population'):
            raise ValueError(f"{request['generator']} has no block population to export")
        params = response['params']
        if not params.get('pop_blocks', params.get('pop_block_scale', 0)) or not params.get('pop_block_proxies', 0):
            raise ValueError('Block population and Minecraft material proxies must both be on')
        positions, colors, shapes = read_stars(output.with_suffix('.stars.bin'))
    cells = np.floor(positions).astype(np.int64)
    if not np.array_equal(positions, (cells + .5).astype(np.float32)):
        raise ValueError('Star positions are not block centers; export needs native block coordinates')
    return cells, block_states(*decode(shapes, colors)), response


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--settings', type=Path, default=ROOT/'config/plot.json')
    parser.add_argument('--script', help='Generator to export (default: saved script)')
    parser.add_argument('--seed', type=int, help='Seed (default: saved seed)')
    parser.add_argument('--out', type=Path, help='Output .schem (default: build/minecraft/<script>-<seed>.schem)')
    args = parser.parse_args()
    request = viewer_request(json.loads(args.settings.read_text(encoding='utf-8')), args.script, args.seed)
    out = args.out or ROOT/'build/minecraft'/f"{request['generator']}-{request['seed']}.schem"
    started = time.perf_counter()
    cells, states, response = generate_blocks(request)
    generated = time.perf_counter()
    data, low, size = schematic(cells, states, out.stem)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_bytes(data)
    names, counts = np.unique(states, return_counts=True)
    report = dict(schematic=str(out), settings=str(args.settings), request=request,
                  data_version=DATA_VERSION, blocks=len(states), origin_cell=low.tolist(),
                  size=size.tolist(), states=dict(zip(names.tolist(), counts.tolist())),
                  generation_s=round(generated-started, 3), encode_s=round(time.perf_counter()-generated, 3),
                  worker=response)
    out.with_suffix('.json').write_text(json.dumps(report, indent=2), encoding='utf-8')
    print(json.dumps({k: report[k] for k in ('schematic', 'blocks', 'size', 'states', 'generation_s', 'encode_s')}, indent=2))


if __name__ == '__main__':
    main()
