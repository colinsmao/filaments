"""Sample the original noise density, then nudge nearby stars toward guide curves.

This preserves random sampling, clumps, diffuse scatter and star identities.
Guides come from the same noise fields; they attract points locally rather than
replacing the distribution with evenly spaced paths. No points are added/deleted.
"""
import colorsys
import numpy as np
import noise_filaments as base
from noise_filament_curves import build_curves
from _alignment import attract_to_curves

NAME = "Noise filaments with alignment"
PARAMETERS = [dict(entry) for entry in base.PARAMETERS] + [
    dict(key="alignment", label="Alignment strength", type="float", default=0.6, min=0.0, max=0.95),
    dict(key="alignment_radius", label="Alignment reach (units)", type="float", default=0.35, min=0.01, max=2.0),
    dict(key="curve_smoothing", label="Guide smoothing", type="float", default=1.0, min=0.0, max=3.0),
    dict(key="guide_layers", label="Guides across Y layer", type="int", default=3, min=1, max=9),
    dict(key="color_alignment", label="Color alignment (0 off, 1 on)", type="int", default=0, min=0, max=1),
]


def generate(count, seed, extent=6.0, frequency=2.0, width=0.065,
             octaves=2, roughness=0.22, clumping=3.0, star_size=0.04, size_variation=0.4,
             y_scale=1.0, fade=0, layer_continuity=1.0, strand_continuity=0.5,
             alignment=0.6, alignment_radius=0.35, curve_smoothing=1.0, color_alignment=0,
             guide_layers=3):
    positions, colors, sizes = base.generate(count, seed, extent, frequency, width,
        octaves, roughness, clumping, star_size, size_variation, y_scale, fade,
        layer_continuity, strand_continuity)
    if alignment <= 0:
        return positions, colors, sizes
    beta = (1 - layer_continuity) + layer_continuity * y_scale * y_scale
    offsets = (np.linspace(-0.65, 0.65, guide_layers)
               if beta < 1 and y_scale > 0 and guide_layers > 1 else [0.0])
    curves = []
    for offset in offsets:
        curves.extend(build_curves(seed, extent, y_scale, frequency, octaves, roughness,
            min_length=2 * alignment_radius, smoothing=curve_smoothing,
            guide_continuity=layer_continuity, guide_offset=float(offset)))
    # Do not attract toward stubs shorter than the diameter of their reach.
    # If no useful guides exist, keep the base cloud unchanged.
    positions, influence, curve_ids = attract_to_curves(positions, curves, alignment, alignment_radius)
    if color_alignment and curves:
        rng = np.random.default_rng(np.random.SeedSequence([seed, 718]))
        palette = np.array([colorsys.hsv_to_rgb(hue, 0.6, 1.0) for hue in rng.random(len(curves))])
        colors = colors * (1 - influence[:, None]) + palette[curve_ids] * influence[:, None]
    return positions, colors, sizes
