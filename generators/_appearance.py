"""Optional artistic point-cloud edits, independent of the source generator."""
import colorsys
import numpy as np
from scipy.spatial import cKDTree
from _alignment import attract_to_curves


def _parameter(key, label, default, low, high, group, toggle=False):
    return dict(key=key, label=label, default=default, min=low, max=high,
                type="int" if toggle else "float", group=group,
                toggle=toggle, enabled_if="" if toggle else {
                    "Sparse curves": "pp_curves", "Merge dense stars": "pp_merge",
                    "Coherent warp": "pp_warp"}[group])


PARAMETERS = [
    _parameter("pp_curves", "Align sparse stars", 0, 0, 1, "Sparse curves", True),
    _parameter("pp_curve_reach", "Attraction reach (units)", .5, .02, 3., "Sparse curves"),
    _parameter("pp_curve_length", "Guide length (units)", 2., .1, 10., "Sparse curves"),
    _parameter("pp_curve_strength", "Alignment strength", .85, 0., 1., "Sparse curves"),
    _parameter("pp_sparse_fraction", "Sparse fraction", .65, .05, 1., "Sparse curves"),
    dict(_parameter("pp_curve_colors", "Color by guide", 0, 0, 1, "Sparse curves", True), enabled_if="pp_curves"),
    _parameter("pp_merge", "Merge dense stars", 0, 0, 1, "Merge dense stars", True),
    _parameter("pp_merge_distance", "Merge distance (units)", .18, .005, 1., "Merge dense stars"),
    _parameter("pp_dense_fraction", "Dense fraction", .3, .05, 1., "Merge dense stars"),
    _parameter("pp_merge_size_boost", "Merged size boost", 2., 1., 8., "Merge dense stars"),
    _parameter("pp_warp", "Warp positions", 0, 0, 1, "Coherent warp", True),
    dict(_parameter("pp_flow_mode", "Flow (0 swirl, 1 waves)", 0, 0, 1, "Coherent warp"), type="int"),
    _parameter("pp_swirl_angle", "Swirl angle (degrees)", 120., -360., 360., "Coherent warp"),
    _parameter("pp_swirl_radius", "Swirl radius (units)", 6., .1, 30., "Coherent warp"),
    _parameter("pp_warp_amount", "Wave amount (units)", .2, 0., 2., "Coherent warp"),
    _parameter("pp_warp_scale", "Wave wavelength (units)", 3., .2, 15., "Coherent warp"),
]


def neighbor_spacing(positions):
    """Distance to the eighth other star: larger means locally more sparse."""
    tree = cKDTree(positions)
    k = min(9, len(positions))
    spacing = tree.query(positions, k=[k], workers=2)[0][:, 0]
    return tree, spacing


def coherent_warp(positions, seed, amount, wavelength, spread=None):
    rng = np.random.default_rng(np.random.SeedSequence([seed, 9410]))
    wavevectors = rng.normal(size=(4, 3))
    wavevectors /= np.linalg.norm(wavevectors, axis=1)[:, None]
    direction = np.cross(wavevectors, rng.normal(size=(4, 3)))
    direction /= np.maximum(np.linalg.norm(direction, axis=1)[:, None], 1e-12)
    # Retain a thin cloud's anisotropy rather than blowing up its short axis.
    spread = np.std(positions, axis=0) if spread is None else np.asarray(spread)
    direction *= spread / max(float(spread.max()), 1e-12)
    phases = positions @ (wavevectors * (2 * np.pi / wavelength)).T + rng.uniform(0, 2*np.pi, 4)
    return (positions + (amount / 4) * np.sin(phases) @ direction).astype(np.float32)


def swirl_warp(positions, angle, radius):
    """Differential rotation around world Y, preserving radius and height.

    This is an exact circular flow map, not attraction toward a spiral line.
    All stars participate; only points on the axis have no rotational motion.
    """
    if angle == 0:
        return positions
    x, z = positions[:, 0].astype(np.float64), positions[:, 2].astype(np.float64)
    theta = np.deg2rad(angle) / (1 + (x*x + z*z) / (radius*radius))
    cosine, sine = np.cos(theta), np.sin(theta)
    result = positions.copy()
    result[:, 0] = cosine*x - sine*z
    result[:, 2] = sine*x + cosine*z
    return result


def align_sparse(positions, colors, seed, tree, spacing, reach, length, strength, fraction, tint=False,
                 cutoff=None):
    if len(positions) < 4 or strength <= 0:
        return positions, colors
    if cutoff is None:
        cutoff = np.quantile(spacing, 1 - fraction)
    eligible = np.flatnonzero(spacing >= cutoff)
    if not len(eligible):
        return positions, colors
    rng = np.random.default_rng(np.random.SeedSequence([seed, 9411]))
    # One random anchor per coarse spatial cell, with a bounded guide budget.
    shuffled = rng.permutation(eligible)
    cells = np.floor(positions[shuffled] / max(reach * 2, length * .5)).astype(np.int64)
    _, first = np.unique(cells, axis=0, return_index=True)
    anchors = shuffled[first]
    if len(anchors) > 1024:
        anchors = rng.choice(anchors, 1024, replace=False)
    _, neighbors = tree.query(positions[anchors], k=min(24, len(positions)), workers=2)
    neighborhood = positions[neighbors].astype(np.float64)
    neighborhood -= neighborhood.mean(axis=1, keepdims=True)
    covariance = np.einsum("nki,nkj->nij", neighborhood, neighborhood)
    eigenvalues, basis = np.linalg.eigh(covariance)
    along = basis[:, :, 2]
    bend = basis[:, :, 1]
    # The bend is predominantly in the local cloud's plane, including thin layers.
    bend *= rng.uniform(-.3, .3, (len(anchors), 1)) * length
    t = np.linspace(-.5, .5, 33)
    curves = (positions[anchors, None, :] + length * t[None, :, None] * along[:, None, :]
              + np.sin(2*np.pi*t)[None, :, None] * bend[:, None, :])
    moved, weight, ids = attract_to_curves(positions[eligible], list(curves), strength, reach)
    # Feather the density selection, avoiding a hard boundary at the sparse cutoff.
    blend = np.clip((spacing[eligible] - cutoff) / max(cutoff * .5, 1e-12), 0, 1)
    if np.ptp(spacing) < 1e-12:
        blend[:] = 1
    result = positions.copy()
    result[eligible] += blend[:, None] * (moved - positions[eligible])
    if tint:
        palette = np.array([colorsys.hsv_to_rgb(h, .6, 1) for h in rng.random(len(anchors))])
        colors = colors.copy()
        influence = (weight * blend)[:, None]
        colors[eligible] = colors[eligible] * (1 - influence) + palette[ids] * influence
    return result, colors


def merge_dense(positions, colors, sizes, seed, spacing, distance, fraction, size_boost=1.):
    """Merge dense stars in randomly oriented bins of diameter <= distance.

    A bounded-bin heuristic avoids chaining an entire filament into one star.
    Centers/colors are volume-weighted; unboosted sizes preserve star volume.
    Return the three arrays plus the number of untouched originals at the front.
    """
    dense = np.flatnonzero(spacing <= np.quantile(spacing, fraction))
    if len(dense) < 2:
        return positions, colors, sizes, len(positions)
    rng = np.random.default_rng(np.random.SeedSequence([seed, 9412]))
    rotation, _ = np.linalg.qr(rng.normal(size=(3, 3)))
    cell_size = distance / np.sqrt(3)
    cells = np.floor(positions[dense] @ rotation / cell_size + rng.random(3)).astype(np.int64)
    _, group, counts = np.unique(cells, axis=0, return_inverse=True, return_counts=True)
    merging = counts[group] > 1
    if not merging.any():
        return positions, colors, sizes, len(positions)
    members, group = dense[merging], group[merging]
    _, group = np.unique(group, return_inverse=True)
    volumes = sizes[members].astype(np.float64) ** 3
    volume = np.bincount(group, weights=volumes)
    centers = np.column_stack([np.bincount(group, weights=volumes * positions[members, axis]) / volume
                               for axis in range(3)])
    color = np.column_stack([np.bincount(group, weights=volumes * colors[members, axis]) / volume
                             for axis in range(3)])
    merged_sizes = np.cbrt(volume)
    # Retain originals for a group that exceeds the viewer's per-star size limit.
    allowed = merged_sizes <= 1000
    # Saturate artistic enlargement without changing membership or star count.
    merged_sizes = np.minimum(merged_sizes * size_boost, 1000)
    keep = np.ones(len(positions), dtype=bool)
    keep[members[allowed[group]]] = False
    return (np.vstack((positions[keep], centers[allowed])).astype(np.float32),
            np.vstack((colors[keep], color[allowed])).astype(np.float32),
            np.concatenate((sizes[keep], merged_sizes[allowed])).astype(np.float32),
            int(keep.sum()))


def apply_appearance(positions, colors, sizes, seed, params, density_source=None):
    if (params.get("pp_curves", 0) or params.get("pp_merge", 0)) and len(positions) > 0:
        tree, spacing = neighbor_spacing(positions)
        fraction = params.get("pp_sparse_fraction", .65)
        cutoff = np.quantile(spacing, 1 - fraction)
        remaining = len(positions)
        if params.get("pp_merge", 0) and len(positions) > 1:
            positions, colors, sizes, remaining = merge_dense(positions, colors, sizes, seed, spacing,
                params.get("pp_merge_distance", .18), params.get("pp_dense_fraction", .3),
                params.get("pp_merge_size_boost", 2.))
            if params.get("pp_curves", 0) and remaining > 0:
                # Combined clumps are fixed landmarks, not small-star neighbors
                # or guide anchors. Reclassify the actual residual population.
                tree, spacing = neighbor_spacing(positions[:remaining])
        if params.get("pp_curves", 0) and remaining > 0 and density_source is not None:
            from _density_alignment import align_to_density
            moved = align_to_density(positions[:remaining], density_source, spacing, cutoff,
                params.get("pp_curve_reach", .5), params.get("pp_density_radius", .25),
                params.get("pp_curve_strength", .85))
            positions = np.concatenate((moved, positions[remaining:]))
        elif params.get("pp_curves", 0) and remaining >= 4:
            moved, tinted = align_sparse(positions[:remaining], colors[:remaining], seed, tree, spacing,
                params.get("pp_curve_reach", .5), params.get("pp_curve_length", 2.),
                params.get("pp_curve_strength", .85), fraction,
                params.get("pp_curve_colors", 0), cutoff=cutoff)
            positions = np.concatenate((moved, positions[remaining:]))
            colors = np.concatenate((tinted, colors[remaining:]))
    # Warp the completed cloud: changing flow must not reselect anchors, recolor
    # guides, or regroup mergers. This makes strength changes directly comparable.
    if params.get("pp_warp", 0):
        if params.get("pp_flow_mode", 0) == 0:
            positions = swirl_warp(positions, params.get("pp_swirl_angle", 120.), params.get("pp_swirl_radius", 6.))
        else:
            positions = coherent_warp(positions, seed, params.get("pp_warp_amount", .2), params.get("pp_warp_scale", 3.))
    return positions, colors, sizes
