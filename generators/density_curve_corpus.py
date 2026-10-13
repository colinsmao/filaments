"""Independent octave-noise corpus -> density selection -> shared star sampler."""
from colorsys import hsv_to_rgb
import numpy as np
from _density_field import PARAMETERS as FIELD_PARAMETERS, build_field
from _axis_controls import FADE_PARAMETERS, SIGNED_Y_FADE_PARAMETERS
from _curve_corpus import build_corpus, score_corpus, footprints, select_candidates, unpack_paths
from _block_population import cell_uniform

NAME = 'Density-selected independent curves'
PRIMITIVE = 'lines'
NATIVE_BLOCKS = True
SHARED_DENSITY_FIELD = True
NATIVE_AXIS_FADE = True
POPULATION_AXIS_FADE = True
PARAMETERS = [dict(p) for p in FIELD_PARAMETERS] + [
    dict(key='corpus_seed', label='Curve corpus seed', type='int', default=173, min=0, max=2147483647),
    dict(key='corpus_cell', label='Candidate grid spacing (blocks)', default=64., min=8., max=512.),
    dict(key='corpus_copies', label='Candidates per grid cell', type='int', default=16, min=1, max=128),
    dict(key='corpus_span', label='Mean baseline span (blocks)', default=128., min=4., max=1024.),
    dict(key='corpus_bend', label='Curve noise amplitude / wavelength', default=.8, min=0., max=3.),
    dict(key='corpus_wavelength', label='Curve noise wavelength (blocks)', default=96., min=8., max=512.),
    dict(key='corpus_octaves', label='Curve noise octaves', type='int', default=3, min=1, max=5),
    dict(key='corpus_roughness', label='Curve octave strength', default=.25, min=0., max=.75),
    dict(key='corpus_vertical', label='Vertical slope / noise fraction', default=.15, min=0., max=1.),
    dict(key='corpus_axis_bias', label='Prefer X/Z headings (0 off)', default=0., min=0., max=1.),
    dict(key='seed_xz', label='XZ anchor region (fraction)', default=1., min=.1, max=1.),
    dict(key='seed_y_pos', label='Y upper anchor bound (fraction)', default=1., min=-1., max=1.),
    dict(key='seed_y_neg', label='Y lower anchor reach (fraction)', default=1., min=-1., max=1.),
    dict(key='select_count', label='Selected curves (maximum)', type='int', default=128, min=1, max=4096),
    dict(key='select_binding', label='Bind curve choice to density (0 off)', default=1., min=0., max=4.),
    dict(key='select_power', label='Selection density contrast', default=.5, min=0., max=3.),
    dict(key='select_continuity', label='Prefer sustained density support', default=1., min=0., max=4.),
    dict(key='select_diversity', label='Discourage coarse overlap (0 off)', default=0., min=0., max=4.),
] + [dict(p) for p in FADE_PARAMETERS if p['key'].startswith('fade_xz')] + [dict(p) for p in SIGNED_Y_FADE_PARAMETERS]
for p in PARAMETERS:
    p.setdefault('type', 'float')


def postprocess_bounds(extent=9.458*16, y_extent=9.458*.234*16, **params):
    return np.zeros(3), np.array([extent, y_extent, extent])


def generate_population_source(count, seed, _return_density=False, **params):
    values = {p['key']: params.get(p['key'], p['default']) for p in PARAMETERS}
    field = {p['key']: values[p['key']] for p in FIELD_PARAMETERS}
    resolution = field.pop('field_resolution')
    density, _, half = build_field(seed, resolution=resolution, **field)
    corpus_seed = int(values['corpus_seed'])
    points, identities = build_corpus(tuple(half), corpus_seed, values['corpus_cell'],
        int(values['corpus_copies']), values['corpus_span'], values['corpus_bend'],
        values['corpus_vertical'], values['corpus_axis_bias'], values['seed_xz'],
        values['seed_y_pos'], values['seed_y_neg'], values['corpus_wavelength'],
        int(values['corpus_octaves']), values['corpus_roughness'])
    if not len(points):
        raise ValueError('No candidate anchors in this region; enlarge the region or increase candidates per cell')
    if values['select_binding'] == 0 and values['select_diversity'] == 0:
        scores, samples = np.ones(len(points)), None
    else:
        scores, samples = score_corpus(points, density, half, values['select_power'], values['select_continuity'])
    footprint = footprints(samples, half, values['corpus_cell']/2) if values['select_diversity'] else None
    selected = select_candidates(scores, identities, values['select_count'], corpus_seed,
                                  values['select_binding'], values['select_diversity'], footprint)
    if not len(selected):
        raise ValueError('No candidates have density support; reduce binding to zero, enlarge the corpus, or change density')
    paths = unpack_paths(points, selected)
    if sum(2*(len(p)-1) for p in paths) > 1_000_000:
        raise ValueError('Selected curves exceed the preview vertex limit; reduce selected count, span or bend')
    hues = [cell_uniform(identities[i:i+1, :3], corpus_seed, 210001+int(identities[i, 3]))[0] for i in selected]
    colors = np.array([hsv_to_rgb(h, .65, 1.) for h in hues])
    vertices = [np.stack((p[:-1], p[1:]), axis=1).reshape(-1, 3) for p in paths]
    positions = np.concatenate(vertices).astype(np.float32)
    rgb = np.concatenate([np.broadcast_to(c, v.shape) for c, v in zip(colors, vertices)]).astype(np.float32)
    result = (positions, rgb, .04), paths, colors
    return (*result, (density, half)) if _return_density else result


def generate_population_density_source(count, seed, **params):
    return generate_population_source(count, seed, _return_density=True, **params)


def generate(count, seed, **params):
    return generate_population_source(count, seed, **params)[0]
