"""Persistent random walks with local blob/filament guidance and free starts."""
import numpy as np
from _guided_walk import walk
from _centerline_selection import select_centerlines

NAME = 'Guided random-walk filaments'
PRIMITIVE = 'lines'
PARAMETERS = [
    dict(key='extent', label='Starting region radius (units)', type='float', default=6., min=1., max=20.),
    dict(key='blob_count', label='Blobs', type='int', default=10, min=0, max=24),
    dict(key='curves_per_blob', label='Walks per blob', type='int', default=5, min=0, max=12),
    dict(key='free_filaments', label='Free filaments (two-way)', type='int', default=15, min=0, max=64),
    dict(key='length', label='Mean filament length (units)', type='float', default=16., min=1., max=30.),
    dict(key='length_variation', label='Length variation', type='float', default=.6, min=0., max=.95),
    dict(key='noise_type', label='Noise (0 Perlin, 1 Simplex2S)', type='int', default=0, min=0, max=1),
    dict(key='noise_scale', label='Noise scale (units)', type='float', default=3., min=.3, max=12.),
    dict(key='octaves', label='Noise octaves', type='int', default=2, min=1, max=4),
    dict(key='roughness', label='Noise roughness', type='float', default=.35, min=0., max=.7),
    dict(key='wandering', label='Noise steering strength', type='float', default=.7, min=0., max=3.),
    dict(key='persistence', label='Heading persistence (units)', type='float', default=.8, min=.15, max=4.),
    dict(key='guide_strength', label='Local guide strength', type='float', default=2.5, min=0., max=6.),
    dict(key='blob_radius', label='Blob influence radius (units)', type='float', default=3., min=0., max=8.),
    dict(key='filament_radius', label='Filament influence radius (units)', type='float', default=1., min=0., max=3.),
    dict(key='capture_radius', label='Blob capture radius (units)', type='float', default=.18, min=0., max=.5),
    dict(key='guide_hold', label='Guide hold distance (units)', type='float', default=1.5, min=.1, max=5.),
    dict(key='free_probability', label='Free-walk probability', type='float', default=.2, min=0., max=1.),
    dict(key='centerline_mode', label='Output (0 walks, 1 centerlines)', type='int', default=1, min=0, max=1),
    dict(key='max_detour', label='Maximum length / endpoint distance', type='float', default=2., min=1., max=5.),
    dict(key='open_centerlines', label='Open centerlines to keep', type='int', default=4, min=0, max=32),
    dict(key='y_scale', label='Y scale fraction', type='float', default=.35, min=0., max=1.),
    dict(key='show_seeds', label='Blob markers (0 off, 1 on)', type='int', default=1, min=0, max=1),
]


def generate_population_source(count, seed, show_seeds=1, centerline_mode=1, max_detour=2., open_centerlines=4, **params):
    paths, blobs, groups, report = walk(seed, **params)
    if centerline_mode:
        paths, groups, _ = select_centerlines(blobs, report, params.get('y_scale', .35), max_detour, open_centerlines)
    palette = np.array([[.45, .75, 1.], [.5, .9, .8], [.7, .65, 1.], [1., .65, .4]])
    path_colors = palette[groups % len(palette)]
    vertices = [np.stack((p[:-1], p[1:]), axis=1).reshape(-1, 3) for p in paths]
    colors = [np.broadcast_to(c, v.shape) for c, v in zip(path_colors, vertices)]
    if show_seeds:
        t = np.linspace(0, 2*np.pi, 33)
        for node in blobs:
            ring = node + .12*np.column_stack((np.cos(t), np.zeros_like(t), np.sin(t)))
            line = np.stack((ring[:-1], ring[1:]), axis=1).reshape(-1, 3)
            vertices.append(line)
            colors.append(np.broadcast_to([1., .9, .4], line.shape))
    positions = np.concatenate(vertices).astype(np.float32)
    return ((positions, np.concatenate(colors).astype(np.float32), np.full(len(positions), .04, dtype=np.float32)),
            paths, path_colors)


def generate(count, seed, **params):
    return generate_population_source(count, seed, **params)[0]
