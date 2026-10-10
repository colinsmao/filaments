"""Noise fields -> explicit curves -> bundles -> regular arc-length star samples.

Uses the same A/B fields as noise_filaments.py, but extracts their actual shared
zero contours. Clump intensity cannot erase faint stretches. This first curve
experiment uses the literal Y slice, without layer-continuity relaxation or fade.
"""
import colorsys
import numpy as np
from scipy.ndimage import gaussian_filter1d
from _noise import grid
from _curves import intersect_fields, curve_length, resample, bundle, allocate_counts
from noise_filaments import build_strand_fields

NAME = "Noise filament curves"
PARAMETERS = [
    dict(key="extent", label="Extent", type="float", default=6.0, min=1.0, max=30.0),
    dict(key="y_scale", label="Y thickness fraction", type="float", default=0.3, min=0.02, max=1.0),
    dict(key="frequency", label="Noise frequency", type="float", default=2.0, min=0.5, max=6.0),
    dict(key="octaves", label="Detail octaves", type="int", default=2, min=1, max=4),
    dict(key="roughness", label="Detail strength", type="float", default=0.22, min=0.0, max=0.6),
    dict(key="min_stars", label="Minimum stars per curve", type="int", default=32, min=2, max=512),
    dict(key="bundle_curves", label="Curves per filament", type="int", default=5, min=1, max=16),
    dict(key="bundle_radius", label="Bundle radius (units)", type="float", default=0.06, min=0.0, max=0.5),
    dict(key="min_length", label="Ignore curves shorter than (units)", type="float", default=0.15, min=0.0, max=2.0),
    dict(key="smoothing", label="Curve smoothing", type="float", default=1.0, min=0.0, max=3.0),
    dict(key="color_curves", label="Color by curve (0 off, 1 on)", type="int", default=1, min=0, max=1),
    dict(key="star_size", label="Star size (units)", type="float", default=0.04, min=0.002, max=0.5),
    dict(key="size_variation", label="Size variation", type="float", default=0.4, min=0.0, max=0.9),
]


def build_curves(seed, extent=6.0, y_scale=0.3, frequency=2.0, octaves=2,
                 roughness=0.22, min_length=0.15, smoothing=1.0, resolution=96):
    points = grid(resolution, y_scale)
    a, b = build_strand_fields(points, seed, frequency, octaves, roughness)
    curves = intersect_fields(a.reshape((resolution,) * 3), b.reshape((resolution,) * 3),
                              np.array([extent, extent * y_scale, extent]))
    result = []
    for curve in curves:
        length = curve_length(curve)
        if length < max(min_length, 1e-8):
            continue
        closed = np.linalg.norm(curve[0] - curve[-1]) < 1e-8
        steps = max(4, min(2048, int(np.ceil(length / (extent / resolution))) + 1))
        regular = resample(curve, steps)
        if smoothing:
            filtered = gaussian_filter1d(regular, smoothing, axis=0, mode="wrap" if closed else "nearest")
            if not closed:
                filtered[0], filtered[-1] = regular[0], regular[-1]
            regular = filtered
        if closed:
            regular = np.vstack((regular, regular[0]))
        result.append(regular)
    return sorted(result, key=curve_length, reverse=True)


def generate(count, seed, extent=6.0, y_scale=0.3, frequency=2.0, octaves=2,
             roughness=0.22, min_stars=32, bundle_curves=5, bundle_radius=0.06,
             min_length=0.15, smoothing=1.0, color_curves=1,
             star_size=0.04, size_variation=0.4):
    curves = build_curves(seed, extent, y_scale, frequency, octaves, roughness, min_length, smoothing)
    if not curves:
        raise ValueError("No curves in this noise slice; try another seed, a thicker Y band, or lower minimum length")
    # All retained centerlines receive stars before allocating satellite curves.
    # At low budgets, prioritize long paths rather than leaving holes in each one.
    limit = max(1, count // min_stars)
    curves = curves[:limit]
    bundles = [bundle(curve, bundle_curves, bundle_radius) for curve in curves]
    paths = [group[i] for i in range(bundle_curves) for group in bundles if i < len(group)][:limit]
    lengths = [curve_length(path) for path in paths]
    counts = allocate_counts(lengths, count, min_stars)
    positions = np.concatenate([resample(path, int(n)) for path, n in zip(paths, counts)])
    rng = np.random.default_rng(np.random.SeedSequence([seed, 718]))
    if color_curves:
        palette = np.array([colorsys.hsv_to_rgb(hue, 0.6, 1.0) for hue in rng.random(len(counts))])
        colors = np.repeat(palette, counts, axis=0)
    else:
        colors = np.broadcast_to([0.55, 0.75, 1.0], positions.shape).copy()
    size_rng = np.random.default_rng(np.random.SeedSequence([seed, 9127]))
    sizes = star_size * size_rng.uniform(1 - size_variation, 1 + size_variation, count)
    return positions, colors, sizes
