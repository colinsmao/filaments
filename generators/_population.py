"""Populate explicit curves by arc length, independently of curve generation."""
import numpy as np

PARAMETERS = [
    dict(key="pop_density", label="Stars per unit length", type="float", default=4., min=0., max=10.),
    dict(key="pop_curve_density_variation", label="Curve density variation", type="float", default=.5, min=0., max=.95),
    dict(key="pop_spread", label="Transverse spread (std dev, units)", type="float", default=.035, min=0., max=.5),
    dict(key="pop_jitter", label="Spacing randomness", type="float", default=.8, min=0., max=1.),
    dict(key="pop_taper", label="Tip taper fraction", type="float", default=.3, min=0., max=1.),
    # Retain the old keys so saved settings carry over to the new density model.
    dict(key="pop_clumping", label="Along-curve density variation", type="float", default=0., min=0., max=6.),
    dict(key="pop_clump_scale", label="Density noise scale (units)", type="float", default=1., min=.1, max=10.),
    dict(key="pop_density_octaves", label="Density noise octaves", type="int", default=3, min=1, max=6),
    dict(key="pop_density_roughness", label="Density noise roughness", type="float", default=.5, min=0., max=1.),
    dict(key="pop_size", label="Star size (units)", type="float", default=.04, min=.002, max=.5),
    dict(key="pop_size_variation", label="Size variation", type="float", default=.4, min=0., max=.9),
    dict(key="pop_colors", label="Use curve colors", type="int", default=0, min=0, max=1, toggle=True),
]
for parameter in PARAMETERS:
    parameter.update(group="Star population", section="population")


def density_noise(s, seed, curve_index, scale, octaves, roughness):
    """One-dimensional gradient noise in arc length, with octave amplitude normalization.

    Each octave doubles frequency and multiplies amplitude by roughness.
    Hashed lattice gradients avoid a finite noise table or world-position input.
    """
    s = np.asarray(s, dtype=float)
    field = np.zeros_like(s)
    amplitude, weight = 1., 0.
    for octave in range(octaves):
        rng = np.random.default_rng(np.random.SeedSequence([seed, 54281, curve_index, octave]))
        q = s / scale * (2 ** octave) + rng.uniform(0, 256)
        lattice = np.floor(q).astype(np.uint64)
        t = q - np.floor(q)
        salt = rng.integers(0, 2**63, dtype=np.uint64)
        def gradient(index):
            h = index + salt
            h = (h ^ (h >> np.uint64(30))) * np.uint64(0xbf58476d1ce4e5b9)
            h = (h ^ (h >> np.uint64(27))) * np.uint64(0x94d049bb133111eb)
            h ^= h >> np.uint64(31)
            return 2. * (h & np.uint64(1)).astype(float) - 1.
        blend = t*t*t * (t * (6*t - 15) + 10)
        field += amplitude * 2 * ((1-blend) * gradient(lattice) * t
                                 + blend * gradient(lattice + np.uint64(1)) * (t-1))
        weight += amplitude
        amplitude *= roughness
        if amplitude == 0:
            break
    return field / weight


def density_distances(quantiles, length, seed, curve_index, params):
    """Invert the normalized integral of exp(variation * noise(s)).

    Numerical integration uses 32 cells per finest noise scale, bounded to
    262144 cells per curve for unusually long external generator paths.
    """
    variation = params.get("pop_clumping", 0.)
    if variation <= 0:
        return quantiles * length
    scale = params.get("pop_clump_scale", 1.)
    octaves = int(params.get("pop_density_octaves", 3))
    roughness = params.get("pop_density_roughness", .5)
    finest = scale / (2 ** (octaves - 1) if roughness > 0 else 1)
    cells = int(np.clip(np.ceil(32 * length / finest), 64, 262144))
    grid = np.linspace(0, length, cells + 1)
    field = density_noise(grid, seed, curve_index, scale, octaves, roughness)
    density = np.exp(variation * (field - field.max()))
    # Uniform grid spacing cancels when normalizing the cumulative integral.
    cumulative = np.r_[0., np.cumsum((density[:-1] + density[1:]) * .5)]
    cumulative /= cumulative[-1]
    return np.interp(quantiles, cumulative, grid)


def populate_curves(paths, path_colors, seed, params, limit=1000000):
    """Stratified samples, Gaussian transverse scatter, and deterministic thinning.

    Density is measured on the displayed curves (after any Y compression).
    Each curve receives an independently seeded mean-density multiplier.
    Along-curve density noise redistributes its fixed candidate count.
    Tip taper removes candidates without redistributing survivors.
    Separate streams keep size, color, taper and spread edits independent.
    """
    colors = np.asarray(path_colors, dtype=float)
    if colors.shape != (len(paths), 3) or not np.isfinite(colors).all() or ((colors < 0) | (colors > 1)).any():
        raise ValueError("Population source needs one valid RGB color per curve")
    curves, lengths, distances = [], [], []
    for path in paths:
        path = np.asarray(path, dtype=float)
        if path.ndim != 2 or path.shape[1] != 3 or len(path) < 2 or not np.isfinite(path).all():
            raise ValueError("Population paths must be finite (N, 3) arrays with at least two vertices")
        if (np.abs(path) > 1e6).any():
            raise ValueError("Population path exceeds coordinate limits")
        keep = np.r_[True, np.linalg.norm(np.diff(path, axis=0), axis=1) > 1e-10]
        path = path[keep]
        distance = np.r_[0., np.cumsum(np.linalg.norm(np.diff(path, axis=0), axis=1))]
        curves.append(path)
        distances.append(distance)
        lengths.append(distance[-1])
    lengths = np.asarray(lengths)
    variation = params.get("pop_curve_density_variation", .5)
    density_factors = np.array([np.random.default_rng(np.random.SeedSequence([seed, 64281, i])).uniform(1-variation, 1+variation)
                                for i in range(len(curves))])
    expected = lengths * params.get("pop_density", 4.) * density_factors
    limited = float(expected.sum()) > limit
    if limited:
        expected *= limit / expected.sum()
    counts = np.floor(expected).astype(int)
    extra = min(limit, int(round(expected.sum()))) - counts.sum()
    order = np.argsort(-(expected - counts), kind="stable")
    counts[order[:extra]] += 1
    all_positions, all_colors, all_sizes = [], [], []
    taper = params.get("pop_taper", .3)
    for i, (path, distance, number) in enumerate(zip(curves, distances, counts)):
        if number == 0 or distance[-1] <= 0:
            continue
        spacing_rng = np.random.default_rng(np.random.SeedSequence([seed, 14281, i]))
        scatter_rng = np.random.default_rng(np.random.SeedSequence([seed, 24281, i]))
        survival_rng = np.random.default_rng(np.random.SeedSequence([seed, 34281, i]))
        size_rng = np.random.default_rng(np.random.SeedSequence([seed, 44281, i]))
        quantiles = (np.arange(number) + .5 + params.get("pop_jitter", .8) * (spacing_rng.random(number) - .5)) / number
        s = density_distances(quantiles, distance[-1], seed, i, params)
        segment = np.minimum(np.searchsorted(distance, s, side="right") - 1, len(path) - 2)
        delta = path[segment + 1] - path[segment]
        segment_length = distance[segment + 1] - distance[segment]
        center = path[segment] + delta * ((s - distance[segment]) / segment_length)[:, None]
        tangent = delta / segment_length[:, None]
        scatter = scatter_rng.normal(size=(number, 3))
        scatter -= (scatter * tangent).sum(axis=1)[:, None] * tangent
        positions = center + params.get("pop_spread", .035) * scatter
        survival = np.ones(number)
        if taper > 0:
            t = np.clip((distance[-1] - s) / (taper * distance[-1]), 0, 1)
            survival *= t * t * (3 - 2*t)
        sizes = params.get("pop_size", .04) * size_rng.uniform(1 - params.get("pop_size_variation", .4),
                                                              1 + params.get("pop_size_variation", .4), number)
        keep = survival_rng.random(number) < survival
        all_positions.append(positions[keep])
        color = colors[i] if params.get("pop_colors", 0) else [.72, .82, 1.]
        all_colors.append(np.broadcast_to(color, (keep.sum(), 3)))
        all_sizes.append(sizes[keep])
    if not all_positions:
        generated = (np.empty((0, 3), dtype=np.float32), np.empty((0, 3), dtype=np.float32), np.empty(0, dtype=np.float32))
    else:
        generated = tuple(np.concatenate(parts).astype(np.float32) for parts in (all_positions, all_colors, all_sizes))
    return generated, dict(population_limited=limited, population_candidates=int(counts.sum()))
