"""Schematic export: proxy decoding, Sponge v2 encoding and worker agreement."""
import gzip
from pathlib import Path
import struct
import sys
import tempfile
import unittest

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT / 'generators'), str(ROOT / 'python'), str(ROOT / 'scripts')]
from _block_population import CANDLE_COLORS, proxy_shapes
import export_schematic as export
import worker


def read_nbt(data):
    """Minimal reader for the tags the exporter writes."""
    position = 0

    def take(n):
        nonlocal position
        chunk = data[position:position + n]
        position += n
        return chunk

    def name():
        return take(struct.unpack('>H', take(2))[0]).decode('utf-8')

    def payload(tag):
        if tag == 2:
            return struct.unpack('>h', take(2))[0]
        if tag == 3:
            return struct.unpack('>i', take(4))[0]
        if tag == 7:
            return take(struct.unpack('>i', take(4))[0])
        if tag == 8:
            return name()
        if tag == 9:
            item, count = struct.unpack('>bi', take(5))
            return [payload(item) for _ in range(count)]
        if tag == 10:
            values = {}
            while (child := take(1)[0]) != 0:
                key = name()
                values[key] = payload(child)
            return values
        if tag == 11:
            count = struct.unpack('>i', take(4))[0]
            return list(struct.unpack(f'>{count}i', take(4 * count)))
        raise ValueError(f'Unexpected tag {tag}')

    tag = take(1)[0]
    root = name()
    values = payload(tag)
    assert position == len(data), 'Trailing bytes after root compound'
    return root, values


def read_varints(data):
    values, value, shift = [], 0, 0
    for byte in data:
        value |= (byte & 0x7f) << shift
        if byte & 0x80:
            shift += 7
        else:
            values.append(value)
            value, shift = 0, 0
    return values


def placed(data):
    """Map each non-air cell (relative to the origin) to its block state."""
    root, values = read_nbt(gzip.decompress(data))
    width, height, length = values['Width'], values['Height'], values['Length']
    indices = np.array(read_varints(values['BlockData'])).reshape(height, length, width)
    names = {i: s for s, i in values['Palette'].items()}
    return root, values, {(int(x), int(y), int(z)): names[indices[y, z, x]]
                          for y, z, x in zip(*np.nonzero(indices))}


class ExportSchematic(unittest.TestCase):
    def test_decoder_inverts_proxy_shapes(self):
        cells = np.stack(np.meshgrid(np.arange(-6, 6), np.arange(-3, 3), np.arange(-6, 6),
                                     indexing='ij'), -1).reshape(-1, 3)
        kinds = np.resize(np.array([0, 0, 0, 1, 2], dtype=np.int8), len(cells))
        tints = np.arange(len(cells)) % len(CANDLE_COLORS)
        shapes = proxy_shapes(cells, kinds, 42, {}).astype('<f4')
        colors = CANDLE_COLORS[tints].astype('<f4')
        colors[kinds == 1], colors[kinds == 2] = [.98, .97, .90], [1., .97, .82]
        decoded, counts, axes, found = export.decode(shapes, colors)
        np.testing.assert_array_equal(decoded, kinds)
        candle, rod = kinds == 0, kinds == 1
        sixteenths = np.rint(shapes[candle, 0] * 16).astype(int)
        np.testing.assert_array_equal(counts[candle], np.searchsorted([2, 4, 5, 6], sixteenths) + 1)
        self.assertEqual(set(counts[candle]), {1, 2, 3, 4})
        np.testing.assert_array_equal(shapes[rod][np.arange(rod.sum()), axes[rod]], 1.)
        self.assertEqual(set(axes[rod]), {0, 1, 2})
        np.testing.assert_array_equal(found[candle], tints[candle])
        states = export.block_states(decoded, counts, axes, found)
        self.assertEqual(states[0], f'{export.CANDLE_BLOCKS[0]}[candles={counts[0]},lit=false,waterlogged=false]')
        self.assertTrue(all(s == export.FULL_BLOCK for s in np.array(states)[kinds == 2]))
        lit = colors.copy()
        lit[candle] *= .5
        with self.assertRaises(ValueError):
            export.decode(shapes, lit)
        with self.assertRaises(ValueError):
            export.decode(np.full((1, 3), .5, dtype='<f4'), colors[:1])

    def test_varints_match_reference_encoding(self):
        def reference(value):
            out = bytearray()
            while True:
                low, value = value & 0x7f, value >> 7
                out.append(low | (0x80 if value else 0))
                if not value:
                    return bytes(out)
        values = [0, 1, 127, 128, 300, 16383, 16384, 2**21 - 1, 2**21, 2**28, 2**32 - 1]
        self.assertEqual(export.varints(values), b''.join(map(reference, values)))
        self.assertEqual(read_varints(export.varints(values)), values)

    def test_sponge_round_trip_with_multibyte_palette(self):
        rng = np.random.default_rng(3)
        cells = np.unique(rng.integers([-20, 5, -11], [20, 14, 12], (400, 3)), axis=0)[:300]
        states = [f'minecraft:test_{i}' for i in range(len(cells))]
        data, low, size = export.schematic(cells, states, 'round trip')
        root, values, blocks = placed(data)
        self.assertEqual(root, 'Schematic')
        self.assertEqual((values['Version'], values['DataVersion']), (2, 5023))
        self.assertEqual([values['Width'], values['Height'], values['Length']], size.tolist())
        self.assertEqual(values['PaletteMax'], len(values['Palette']))
        self.assertEqual(values['Palette']['minecraft:air'], 0)
        self.assertGreater(len(values['Palette']), 128)
        self.assertEqual(values['Metadata']['Name'], 'round trip')
        np.testing.assert_array_equal(low, cells.min(axis=0))
        self.assertEqual(blocks, {tuple(map(int, c - low)): s for c, s in zip(cells, states)})
        self.assertEqual(data, export.schematic(cells, states, 'round trip')[0])

    def test_export_matches_worker_blocks_and_lighting_changes_only_color(self):
        params = dict(seed_rate=20., strand_length=70., seed_xz=.9, seed_y_pos=.9, seed_y_neg=.9,
                      select_budget=4., select_density=0., select_rod_attraction=2., pop_lighting=1)
        cfg = dict(block_units=True, legacy_display_scale=16., generator=dict(
            script='density_population_selection', seed=42, count=100,
            density_field=dict(extent=96., y_extent=24., field_resolution=24),
            parameters={'density_population_selection': params}))
        request = export.viewer_request(cfg)
        self.assertEqual((request['params']['pop_lighting'], request['params']['pop_colors']), (0, 0))
        self.assertEqual(params['pop_lighting'], 1)
        cells, states, response = export.generate_blocks(request)
        self.assertEqual(len(states), response['star_count'])
        self.assertEqual(len(np.unique(cells, axis=0)), len(cells))
        allowed = {f'{b}[candles={n},lit=false,waterlogged=false]' for b in export.CANDLE_BLOCKS for n in range(1, 5)}
        allowed |= {f'minecraft:end_rod[facing={f}]' for f in export.ROD_FACING} | {export.FULL_BLOCK}
        self.assertLessEqual(set(states), allowed)
        self.assertTrue(any('candle' in s for s in states))
        if response['selection_stats']['rods']:
            self.assertTrue(any('end_rod' in s for s in states))
        data, low, _ = export.schematic(cells, states, 'e2e')
        _, _, blocks = placed(data)
        self.assertEqual(blocks, {tuple(map(int, c - low)): s for c, s in zip(cells, states)})
        with tempfile.TemporaryDirectory() as directory:
            records = []
            for lighting in (0, 1):
                output = Path(directory) / f'{lighting}.bin'
                lit = worker.generate_request(dict(request, params=dict(request['params'], pop_lighting=lighting)),
                                              ROOT / 'generators', output)
                self.assertTrue(lit['ok'], lit.get('error'))
                records.append(np.frombuffer(output.with_suffix('.stars.bin').read_bytes()[16:], '<f4').reshape(-1, 10))
        np.testing.assert_array_equal(records[0][:, [0, 1, 2, 6, 7, 8, 9]], records[1][:, [0, 1, 2, 6, 7, 8, 9]])
        self.assertFalse(np.array_equal(records[0][:, 3:6], records[1][:, 3:6]))

    def test_scaffold_without_population_is_refused(self):
        request = export.viewer_request(dict(generator=dict(script='block_scaffold', seed=42, count=100,
                                                            parameters={'block_scaffold': dict(root_count=1)})))
        with self.assertRaises(ValueError):
            export.generate_blocks(request)


if __name__ == '__main__':
    unittest.main()
