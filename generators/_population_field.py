"""Arc-density profiles from the upstream field, shared by both star samplers."""
import numpy as np
from scipy.ndimage import map_coordinates


def field_profiles(paths, arcs, seed, params, source):
    if '_population_profiles' in params:
        profiles = params['_population_profiles']
        if profiles is not None and len(profiles) != len(paths):
            raise ValueError('Population profiles must match selected paths')
        return profiles
    from _population_context import curve_ids
    identities = curve_ids(params, len(paths))
    strength = params.get('pop_source_density', 0.)
    if strength <= 0 or source is None:
        return None
    from _population import density_noise
    density, half = source
    density, half = np.asarray(density), np.asarray(half)
    cell = 2*half/(np.array(density.shape)-1)
    variation = params.get('pop_clumping', 0.)
    noise_scale = params.get('pop_clump_scale', 1.)
    octaves = int(params.get('pop_density_octaves', 3))
    roughness = params.get('pop_density_roughness', .5)
    peak = max(float(density.max()), 1e-30)
    profiles, total_length, total_weight = [], 0., 0.
    for i, (path, arc) in enumerate(zip(paths, arcs)):
        length = arc[-1]
        # Measure travel in grid cells along the actual path. A thin Y extent
        # must not force excessive sampling of a mostly horizontal curve.
        voxel_arc = np.r_[0., np.cumsum(np.linalg.norm(np.diff(path, axis=0)/cell, axis=1))]
        count = int(np.clip(np.ceil(4*voxel_arc[-1]), 64, 262144))
        distance = np.interp(np.linspace(0, voxel_arc[-1], count+1), voxel_arc, arc)
        if variation > 0:
            step = noise_scale/(32*2**(octaves-1 if roughness > 0 else 0))
            noise_count = int(np.clip(np.ceil(length/max(step, 1e-12)), 64, 262144))
            distance = np.r_[distance, np.linspace(0, length, noise_count+1)]
        distance = np.unique(np.r_[distance, arc])
        center = np.column_stack([np.interp(distance, arc, path[:, axis]) for axis in range(3)])
        coordinates = ((center/half + 1)*.5*(np.array(density.shape)-1)).T
        sampled = map_coordinates(density, coordinates, order=1, mode='nearest')
        weight = np.maximum(sampled/peak, 0.)**strength
        total_length += length
        total_weight += np.trapz(weight, distance)
        if variation > 0:
            noise = density_noise(distance, seed, int(identities[i]), noise_scale, octaves, roughness)
            noise = np.exp(variation*(noise-noise.max()))
            noise *= length/max(np.trapz(noise, distance), 1e-30)
            weight *= noise
        cumulative = np.r_[0., np.cumsum(np.diff(distance)*(weight[:-1]+weight[1:])*.5)]
        integral = cumulative[-1]
        if integral > 0:
            cumulative /= integral
        profiles.append((distance, cumulative, integral/max(length, 1e-30)))
    # One normalization across ALL curves: dense curves may gain stars while
    # sparse ones lose them. Per-curve normalization would erase this effect.
    reference = total_weight/max(total_length, 1e-30)
    return [(s, cdf, mean/reference if reference > 0 else 0.) for s, cdf, mean in profiles]


def sample_profile(quantiles, profile):
    distance, cumulative, _ = profile
    return np.interp(quantiles, cumulative, distance)
