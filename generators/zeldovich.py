"""Direct Zel'dovich-style displacement of initially uniform particles.

Gaussian initial density -> inverse-Laplacian gradient -> x = q + D*s(q).
No force integration or time-stepping. Positions wrap in a periodic box. This
is an artistic spectrum, not a calibrated cosmological model; after crossing,
particles pass through each other rather than forming bound objects.
"""
import numpy as np
from scipy import fft
from scipy.ndimage import gaussian_filter, map_coordinates
from scipy.stats import qmc
from _postprocess import suppress_voids

NAME = "Zeldovich displacement"
PARAMETERS = [
    dict(key="extent", label="Extent", type="float", default=6.0, min=1.0, max=30.0),
    dict(key="structure_scale", label="Structure scale (units)", type="float", default=3.0, min=0.5, max=12.0),
    dict(key="evolution", label="Evolution strength", type="float", default=1.8, min=0.0, max=4.0),
    dict(key="void_threshold", label="Void threshold (mean density)", type="float", default=1.0, min=0.0, max=4.0),
    dict(key="detail", label="Small-scale detail", type="float", default=0.25, min=0.0, max=1.0),
    dict(key="y_scale", label="Y scale fraction", type="float", default=1.0, min=0.02, max=1.0),
    dict(key="star_size", label="Star size (units)", type="float", default=0.04, min=0.002, max=0.5),
    dict(key="size_variation", label="Size variation", type="float", default=0.4, min=0.0, max=0.9),
]


def _wavevectors(resolution):
    full = fft.fftfreq(resolution).astype(np.float32) * resolution * (2 * np.pi)
    half = fft.rfftfreq(resolution).astype(np.float32) * resolution * (2 * np.pi)
    return full[:, None, None], full[None, :, None], half[None, None, :]


def displacement_from_density(density):
    """Unit-box displacement with divergence(s) = -density, zero mean motion."""
    n = density.shape[0]
    wavevectors = _wavevectors(n)
    k2 = sum(k * k for k in wavevectors)
    spectrum = fft.rfftn(density, workers=2)
    spectrum[0, 0, 0] = 0
    inverse = np.zeros_like(k2)
    np.divide(1, k2, out=inverse, where=k2 > 0)
    fields = []
    for axis, k in enumerate(wavevectors):
        gradient = (1j * k * inverse * spectrum).astype(np.complex64)
        # An odd derivative has no real-valued Nyquist component on an even grid.
        if n % 2 == 0:
            slices = [slice(None)] * 3
            slices[axis] = n // 2
            gradient[tuple(slices)] = 0
        fields.append(fft.irfftn(gradient, s=density.shape, workers=2).astype(np.float32))
    return fields


def build_displacement(seed, extent=6.0, structure_scale=3.0, detail=0.25, resolution=96):
    rng = np.random.default_rng(np.random.SeedSequence([seed, 801]))
    white = rng.standard_normal((resolution,) * 3, dtype=np.float32)
    spectrum = fft.rfftn(white, workers=2)
    k = np.sqrt(sum(axis * axis for axis in _wavevectors(resolution))) / (2 * np.pi)
    # Broad spectrum with a controllable small-scale cutoff, in cycles per box.
    # Cap unresolved frequencies rather than aliasing them into coarse features.
    cutoff = np.clip((2 * extent) / structure_scale, 1, resolution / 12)
    coarse = np.exp(-0.5 * (k / cutoff) ** 2)
    fine = np.exp(-0.5 * (k / (cutoff * 3)) ** 2)
    spectrum *= np.sqrt(k) * (coarse + 0.35 * detail * fine)
    spectrum[0, 0, 0] = 0
    density = fft.irfftn(spectrum, s=white.shape, workers=2)
    density /= max(float(density.std()), 1e-12)
    return displacement_from_density(density)


def initial_particles(count, seed):
    # Low-discrepancy samples with cell-scale jitter start nearly uniform without
    # structured projections. The same seed/count retains identities as D changes.
    rng = np.random.default_rng(np.random.SeedSequence([seed, 802]))
    sampler = qmc.Sobol(3, scramble=True, seed=int(rng.integers(0, 2147483647)))
    q = sampler.random_base2((count - 1).bit_length())[:count]
    q += rng.uniform(-0.5, 0.5, (count, 3)) / np.cbrt(count)
    return (q % 1).astype(np.float32) % 1


def _sample_periodic(field, positions):
    return map_coordinates(field, positions.T * field.shape[0], order=1,
                           mode="grid-wrap", prefilter=False)


def postprocess_bounds(extent=6.0, y_scale=1.0, **params):
    return (0, 0, 0), (extent, extent * y_scale, extent)


def _concentrate(positions, count, seed, threshold, resolution=64):
    """Sample the soft-filtered final density using periodic linear tents.

    Fresh continuous samples avoid duplicate particles and block-shaped cells.
    This is an artistic density postprocess, not additional gravitational motion.
    """
    indices = np.floor(positions * resolution).astype(int) % resolution
    flat = (indices[:, 0] * resolution + indices[:, 1]) * resolution + indices[:, 2]
    mass = np.bincount(flat, minlength=resolution**3).reshape((resolution,) * 3)
    density = gaussian_filter(mass.astype(np.float64), 1.0, mode="wrap")
    weights = suppress_voids(density, threshold)
    rng = np.random.default_rng(np.random.SeedSequence([seed, 803]))
    selected = rng.choice(weights.size, size=count, p=weights.ravel() / weights.sum())
    centers = np.column_stack(np.unravel_index(selected, weights.shape)) + 0.5
    jitter = rng.random((count, 3)) - rng.random((count, 3))
    return (((centers + jitter) / resolution) % 1).astype(np.float32) % 1


def generate(count, seed, extent=6.0, structure_scale=3.0, evolution=1.8,
             detail=0.25, y_scale=1.0, star_size=0.04, size_variation=0.4,
             void_threshold=1.0):
    # A minimum pilot population avoids amplifying shot noise at small counts.
    # Threshold 0 bypasses postprocessing and preserves the original output.
    population = max(count, 262144) if void_threshold > 0 else count
    q = initial_particles(population, seed)
    positions = q.copy()
    if evolution != 0:
        displacement = build_displacement(seed, extent, structure_scale, detail)
        for axis in range(3):
            positions[:, axis] += evolution * _sample_periodic(displacement[axis], q)
        positions %= 1

    if void_threshold > 0:
        positions = _concentrate(positions, count, seed, void_threshold)

    # Color by the actual final concentration, including overlapping streams.
    # This is display-only: it does not move stars or alter their sizes.
    color_resolution = 48
    indices = np.floor(positions * color_resolution).astype(int) % color_resolution
    flat = (indices[:, 0] * color_resolution + indices[:, 1]) * color_resolution + indices[:, 2]
    mass = np.bincount(flat, minlength=color_resolution**3).reshape((color_resolution,) * 3).astype(np.float32)
    mass = gaussian_filter(mass, 1.0, mode="wrap")
    relative_density = _sample_periodic(mass, positions) / (count / color_resolution**3)
    warmth = np.clip(np.log1p(relative_density) / np.log(16), 0, 1)[:, None]
    colors = (1 - warmth) * np.array([0.45, 0.65, 1.0]) + warmth * np.array([1.0, 0.86, 0.58])

    positions = (positions * 2 - 1) * extent
    positions[:, 1] *= y_scale
    rng = np.random.default_rng(np.random.SeedSequence([seed, 9127]))
    sizes = star_size * rng.uniform(1 - size_variation, 1 + size_variation, count)
    return positions, colors, sizes
