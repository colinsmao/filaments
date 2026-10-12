"""Shared upstream A/B/C noise and density field, independent of its consumers."""
import numpy as np
from _postprocess import remap_density
from _noise import fractal_noise, grid
from noise_filaments import _clump_log_weight

# One schema and one saved configuration in blocks for both consumers.
PARAMETERS = [
    dict(key='extent', label='XZ half-extent (blocks)', default=9.458*16, min=1., max=3840.),
    dict(key='y_extent', label='Y half-extent (blocks)', default=9.458*.234*16, min=.01, max=3840.),
    dict(key='noise_scale', label='Noise wavelength (blocks)', default=9.458/2.505*16, min=.1, max=7680.),
    dict(key='field_resolution', label='Noise grid resolution', type='int', default=48, min=24, max=96),
    dict(key='width', label='Density support width (noise units)', default=.025, min=.025, max=.25),
    dict(key='octaves', label='Detail octaves', type='int', default=2, min=1, max=4),
    dict(key='roughness', label='Detail strength', default=.107, min=0., max=.6),
    dict(key='clumping', label='Clump contrast', default=6.875, min=0., max=12.),
    dict(key='strand_continuity', label='Strand continuity', default=1., min=0., max=1.),
    *(dict(key='density_'+part, label='Density '+part+' slope', default=1., min=.05, max=3.)
      for part in ('low', 'mid', 'high')),
    dict(key='broad_strength', label='Broad density strength (0 off)', default=4., min=0., max=12.),
    dict(key='broad_scale', label='Broad density scale (base wavelengths)', default=2., min=2., max=8.),
]
for entry in PARAMETERS:
    entry.setdefault('type', 'float')
    entry.update(scope='density_field', group='Noise / density field', section='field')
KEYS = {entry['key'] for entry in PARAMETERS}


def build_field(seed, extent, y_extent, noise_scale, resolution=96, **params):
    """Evaluate the upstream field over physical block bounds at a wavelength."""
    if not np.isfinite(noise_scale) or noise_scale <= 0:
        raise ValueError('Noise wavelength must be finite and positive')
    density, fields = build_density(seed, frequency=extent/noise_scale,
        y_scale=y_extent/extent, _resolution=resolution, _return_fields=True, **params)
    return density, fields, np.array([extent, y_extent, extent])

def _strand_log_density(a, b, c, width):
    denominator = 2 * width * width
    # Symmetric union of all three pairs. Log space avoids underflow in voids.
    ab = -(a * a + b * b) / denominator
    ac = -(a * a + c * c) / denominator
    bc = -(b * b + c * c) / denominator
    return np.logaddexp(ab, np.logaddexp(ac, bc))


def build_density(seed, frequency=2.0, width=0.065, octaves=2, roughness=0.22,
                  clumping=3.0, y_scale=1.0, strand_continuity=0.0,
                  density_low=1.0, density_mid=1.0, density_high=1.0,
                  broad_strength=4.0, broad_scale=2.0, _return_fields=False, _resolution=96):
    """Shared symmetric three-field density, remapped but not edge-faded."""
    resolution = int(_resolution)
    points = grid(resolution, y_scale)
    a = fractal_noise(points, np.random.SeedSequence([seed, 101]), frequency, octaves, roughness)
    b = fractal_noise(points, np.random.SeedSequence([seed, 202]), frequency, octaves, roughness)
    c = fractal_noise(points, np.random.SeedSequence([seed, 404]), frequency, octaves, roughness)
    knots = fractal_noise(points, np.random.SeedSequence([seed, 303]), frequency * 0.6, 2)
    log_density = (_strand_log_density(a, b, c, width)
                   + _clump_log_weight(knots, clumping, strand_continuity))
    density = np.exp(log_density - log_density.max()).reshape((resolution,) * 3)
    density = remap_density(density, density_low, density_mid, density_high)
    if broad_strength > 0:
        # A separate coarser octave reweights existing fine structures. Keep
        # A/B/C and clump streams untouched, and bypass exactly at strength 0.
        broad = fractal_noise(points, np.random.SeedSequence([seed, 505]),
                              frequency/broad_scale, 1).reshape(density.shape)
        # The common scale cancels when sampling; subtract max for stability.
        density = density * np.exp(broad_strength*(broad-broad.max()))
    if _return_fields:
        return density, np.stack((a, b, c)).reshape((3, resolution, resolution, resolution))
    return density


