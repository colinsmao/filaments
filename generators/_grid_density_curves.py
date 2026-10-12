"""Coordinate-hashed block births and budget-limited growth on pair-zero guides."""
import numpy as np
from scipy.spatial import cKDTree
from scipy.special import betaincinv
from _block_population import cell_uniform
from _stable_density_curves import sample_support, clip_path

PARAMETERS = [
    dict(key='seed_rate', label='Mean seeds per million blocks', type='float', default=500., min=0., max=10000., slider_max=100.),
    dict(key='seed_density_power', label='Seed density power (0 = uniform)', type='float', default=1., min=0., max=4.),
    dict(key='length_variation', label='Curve length variation', type='float', default=.5, min=0., max=1.),
    dict(key='seed_y_pos', label='Y upper seed bound (fraction)', type='float', default=.65, min=-1., max=1.),
    dict(key='seed_y_neg', label='Y lower seed reach (fraction)', type='float', default=.65, min=-1., max=1.),
]


def _mean_seed_weight(density, half, low, shape, power):
    """Exact block-center mean of powered trilinear density, using bounded planes."""
    # Slice along the longest block axis to keep temporary planes small. Reuse
    # interpolated field planes while block centers remain in the same grid cell.
    order = np.argsort(-shape)
    field = np.transpose(density, order)
    indices, fractions = [], []
    for axis, n in zip(order, field.shape):
        centers = np.arange(shape[axis]) + low[axis] + .5
        coords = np.clip((centers/half[axis]+1)*.5*(n-1), 0, n-1)
        index = np.minimum(coords.astype(np.int64), n-2)
        indices.append(index)
        fractions.append(coords-index)
    ix, iy, iz = indices
    fx, fy, fz = fractions
    def plane(i):
        row = field[i]
        along_z = row[:, iz]*(1-fz) + row[:, iz+1]*fz
        return along_z[iy]*(1-fy[:, None]) + along_z[iy+1]*fy[:, None]
    total, previous = 0., -1
    for i, t in zip(ix, fx):
        if i != previous:
            a, b = plane(i), plane(i+1)
            previous = i
        total += np.sum(np.clip(a*(1-t)+b*t, 0., 1.)**power)
    return total/int(np.prod(shape))


def block_seeds(density, half, seed, rate, power=1., seed_xz=.65, seed_y=.65,
                seed_y_pos=None, seed_y_neg=None):
    """Coordinate hash against rate/1M * weight/mean(weight), capped at one."""
    if rate <= 0:
        return np.empty((0, 3), dtype=np.int64)
    positive = np.asarray(half)*[seed_xz, seed_y if seed_y_pos is None else seed_y_pos, seed_xz]
    negative = np.asarray(half)*[seed_xz, seed_y if seed_y_neg is None else seed_y_neg, seed_xz]
    low = np.ceil(-negative-.5).astype(np.int64)
    high = np.floor(positive-.5).astype(np.int64)
    shape = np.maximum(high-low+1, 0)
    total = int(np.prod(shape))
    if total > 100_000_000:
        raise ValueError('Seed region exceeds 100 million block centers; reduce its extents or region fractions')
    peak = max(float(np.max(density)), 1e-30)
    selected, count = [], 0
    if not total:
        return np.empty((0, 3), dtype=np.int64)
    mean_weight = (_mean_seed_weight(density/peak, np.asarray(half), low, shape, power)
                   if power > 0 else 1.)
    if mean_weight <= 0:
        return np.empty((0, 3), dtype=np.int64)
    # Same coordinate hash as cell_uniform, evaluated on axis products. Only
    # construct XYZ records for hash survivors, not every block in the volume.
    axis_hash = [np.arange(low[i], high[i]+1, dtype=np.int64).astype(np.uint64)*np.uint64(k)
                 for i, k in enumerate((0x9e3779b97f4a7c15, 0xbf58476d1ce4e5b9, 0x94d049bb133111eb))]
    yz = (axis_hash[1][:, None] ^ axis_hash[2][None, :]).ravel()
    slab = max(1, 65536//len(yz))
    probability = rate*1e-6/mean_weight
    for start in range(0, int(shape[0]), slab):
        h = (axis_hash[0][start:start+slab, None] ^ yz[None, :]).ravel()
        h ^= np.uint64(seed) ^ np.uint64(75281+17611)
        h ^= h >> np.uint64(30)
        h *= np.uint64(0xbf58476d1ce4e5b9)
        h ^= h >> np.uint64(27)
        h *= np.uint64(0x94d049bb133111eb)
        h ^= h >> np.uint64(31)
        draws = (h >> np.uint64(11)).astype(float)*(1./2**53)
        selected_index = np.flatnonzero(draws < probability)
        x, remainder = np.divmod(selected_index, len(yz))
        y, z = np.divmod(remainder, shape[2])
        cells = np.column_stack((x+start, y, z)) + low
        draws = draws[selected_index]
        if power > 0:
            rho = np.clip(sample_support(density, cells+.5, half)/peak, 0., 1.)
            cells = cells[draws < probability*rho**power]
        count += len(cells)
        if count > 8192:
            raise ValueError('More than 8192 seeds accepted; reduce Seed rate or the seed region')
        selected.append(cells)
    return np.concatenate(selected) if selected else np.empty((0, 3), dtype=np.int64)


def project_seeds(paths, cells):
    """Exact nearest-segment projection, using midpoint bounds to prune searches."""
    arcs = [np.r_[0., np.cumsum(np.linalg.norm(np.diff(p, axis=0), axis=1))] for p in paths]
    starts = np.concatenate([p[:-1] for p in paths])
    delta = np.concatenate([np.diff(p, axis=0) for p in paths])
    lengths = np.linalg.norm(delta, axis=1)
    owners = np.concatenate([np.full(len(p)-1, i, dtype=int) for i, p in enumerate(paths)])
    offsets = np.concatenate([a[:-1] for a in arcs])
    tree = cKDTree(starts+delta*.5)
    max_radius = lengths.max()*.5
    selected_owner, selected_arc = [], []
    for point in cells+.5:
        _, nearest = tree.query(point)
        t = np.clip(np.dot(point-starts[nearest], delta[nearest])/max(lengths[nearest]**2, 1e-30), 0, 1)
        distance = np.linalg.norm(point-starts[nearest]-t*delta[nearest])
        candidates = np.asarray(sorted(tree.query_ball_point(point, distance+max_radius+1e-8)))
        d = delta[candidates]
        t = np.clip(np.einsum('ij,ij->i', point-starts[candidates], d)/np.maximum(lengths[candidates]**2, 1e-30), 0, 1)
        error = np.sum((point-starts[candidates]-t[:, None]*d)**2, axis=1)
        best = np.argmin(error)
        segment = candidates[best]
        selected_owner.append(owners[segment])
        selected_arc.append(offsets[segment]+t[best]*lengths[segment])
    return arcs, np.asarray(selected_owner), np.asarray(selected_arc)


def grow_intervals(roots, budgets, total, closed=False, identities=None):
    """Simultaneous two-tip growth; contacts merge only within max budget.

    A merged component inherits remaining outer tips, never restarts a stopped
    tip, and never sums budgets. Failed joins stop the two contacting tips.
    """
    identities = np.arange(len(roots)) if identities is None else identities
    order = np.lexsort((identities, roots))
    parts = [dict(left=float(roots[i]), right=float(roots[i]), budget=float(budgets[i]),
                  lo=True, hi=True, owner=int(identities[i]), seeds=1) for i in order]
    tolerance = max(total, 1.)*1e-10
    while parts:
        times = []
        for part in parts:
            length = part['right']-part['left']
            remaining = min(part['budget'], total)-length
            if remaining <= tolerance:
                part['lo'] = part['hi'] = False
            if not closed:
                if part['left'] <= tolerance: part['lo'] = False
                if total-part['right'] <= tolerance: part['hi'] = False
            speed = int(part['lo'])+int(part['hi'])
            if speed:
                times.append(remaining/speed)
                if not closed:
                    if part['lo']: times.append(part['left'])
                    if part['hi']: times.append(total-part['right'])
        if not times:
            break
        pairs = len(parts) if closed and len(parts) > 1 else len(parts)-1
        for i in range(pairs):
            a, b = parts[i], parts[(i+1) % len(parts)]
            speed = int(a['hi'])+int(b['lo'])
            if speed:
                gap = b['left']+(total if i == len(parts)-1 else 0)-a['right']
                times.append(max(0., gap)/speed)
        dt = max(0., min(times))
        for part in parts:
            part['left'] -= dt*part['lo']
            part['right'] += dt*part['hi']
        # Resolve simultaneous contacts in fixed seed-identity order.
        contacts = []
        for i in range(pairs):
            a, b = parts[i], parts[(i+1) % len(parts)]
            gap = b['left']+(total if i == len(parts)-1 else 0)-a['right']
            if gap <= tolerance and (a['hi'] or b['lo']):
                contacts.append((min(a['owner'], b['owner']), a, b))
        for part in parts:
            if part['right']-part['left'] >= min(part['budget'], total)-tolerance:
                part['lo'] = part['hi'] = False
        for _, a, b in sorted(contacts, key=lambda x: x[0]):
            if not any(p is a for p in parts) or not any(p is b for p in parts):
                continue
            wrap = a is parts[-1] and b is parts[0]
            right = b['right']+(total if wrap else 0)
            budget = max(a['budget'], b['budget'])
            if right-a['left'] <= budget+tolerance:
                winner = min((a, b), key=lambda p: (-p['budget'], p['owner']))
                merged = dict(left=a['left'], right=right, budget=budget,
                              lo=a['lo'], hi=b['hi'], owner=winner['owner'], seeds=a['seeds']+b['seeds'])
                index = next(i for i, p in enumerate(parts) if p is a)
                if wrap:
                    parts = parts[1:-1]+[merged]
                else:
                    parts[index:index+2] = [merged]
            else:
                a['hi'] = b['lo'] = False
    return parts


def seed_curves(paths, cells, seed, mean_length, variation=.5):
    if not paths or not len(cells):
        return [], np.empty((0, 3), dtype=np.int64), []
    arcs, owners, roots = project_seeds(paths, cells)
    draws = betaincinv(2., 2., cell_uniform(cells, seed, stream=17612))
    budgets = mean_length*(1+variation*(2*draws-1))
    result, identities, reports = [], [], []
    for owner in np.unique(owners):
        chosen = np.flatnonzero(owners == owner)
        path, arc = paths[owner], arcs[owner]
        total = arc[-1]
        closed = np.linalg.norm(path[0]-path[-1]) < 1e-8
        parts = grow_intervals(roots[chosen], budgets[chosen], total, closed, chosen)
        for part in parts:
            a, b = part['left'], part['right']
            if b-a <= 1e-8:
                continue
            if closed:
                length = min(b-a, total)
                a %= total
                b = a+length
                geometry = clip_path(path, arc, a, min(b, total))
                if b > total:
                    geometry = np.vstack((geometry, clip_path(path, arc, 0, b-total)[1:]))
            else:
                geometry = clip_path(path, arc, max(0, a), min(b, total))
            result.append(geometry)
            identities.append(cells[part['owner']])
            reports.append(part)
    return result, np.asarray(identities), reports
