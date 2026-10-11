"""Select a readable skeleton from completed walks; never prescribe routes."""
import numpy as np
from scipy.ndimage import gaussian_filter1d


def smooth_path(path, width=.2):
    """Small arc-length smoothing with exact endpoint preservation."""
    lengths = np.linalg.norm(np.diff(path, axis=0), axis=1)
    keep = np.r_[True, lengths > 1e-10]
    path = path[keep]
    distance = np.r_[0., np.cumsum(np.linalg.norm(np.diff(path, axis=0), axis=1))]
    if len(path) < 3 or distance[-1] <= 1e-10:
        return path
    s = np.linspace(0, distance[-1], max(3, int(np.ceil(distance[-1]/.08))+1))
    regular = np.column_stack([np.interp(s, distance, path[:, axis]) for axis in range(3)])
    smoothed = gaussian_filter1d(regular, width/(s[1]-s[0]), axis=0, mode='nearest')
    t = (s/s[-1])[:, None]
    smoothed += (1-t)*(path[0]-smoothed[0]) + t*(path[-1]-smoothed[-1])
    smoothed[0], smoothed[-1] = path[0], path[-1]
    return smoothed


def select_centerlines(blobs, report, y_scale=.35, max_detour=2., open_count=4):
    """One shortest encountered route per unordered blob pair, plus a few open paths.

    Both arrival directions are equivalent. A free two-way walk qualifies as a
    link only when both halves actually hit different blobs. Selection never
    invents an edge or moves endpoints. Metrics precede Y compression.
    """
    groups = report['initial_groups']
    captures = report['captured']
    halves = report['half_paths']
    connections, open_paths = {}, []
    examined = 0
    for group in np.unique(groups):
        ids = np.flatnonzero(groups == group)
        if group < len(blobs):
            candidates = [(int(group), int(captures[i]), np.asarray(halves[i]), int(i)) for i in ids]
        else:
            a, b = ids
            path = np.concatenate((np.asarray(halves[b])[::-1], np.asarray(halves[a])[1:]))
            candidates = [(int(captures[b]), int(captures[a]), path, int(a))]
        for a, b, path, identity in candidates:
            examined += 1
            arc = float(np.linalg.norm(np.diff(path, axis=0), axis=1).sum())
            chord = float(np.linalg.norm(path[-1]-path[0]))
            if arc <= 1e-10 or chord <= 1e-10 or arc/chord > max_detour:
                continue
            if a >= 0 and b >= 0:
                if a == b:
                    continue
                key = tuple(sorted((a, b)))
                if key not in connections or arc < connections[key][0]:
                    connections[key] = (arc, path, int(group), identity)
            else:
                # Prefer genuine free-start strands; then keep the least winding
                # routes. This is a display selection, not an influence on growth.
                open_paths.append((group < len(blobs), arc/chord, identity, path, int(group)))
    chosen = [(value[1], value[2], value[3]) for _, value in sorted(connections.items())]
    loose = sorted(open_paths, key=lambda item: item[:3])[:int(open_count)]
    chosen.extend((item[3], item[4], item[2]) for item in loose)
    if not chosen:
        raise ValueError('No centerlines survived selection; allow open centerlines, increase maximum detour, or explore more walks')
    scale = np.array([1., y_scale, 1.])
    return ([smooth_path(path)*scale for path, _, _ in chosen],
            np.array([group for _, group, _ in chosen]),
            dict(discovered_links=len(connections), open_centerlines=len(loose), candidates=examined,
                 selected_ids=[identity for _, _, identity in chosen], blob_pairs=list(sorted(connections))))
