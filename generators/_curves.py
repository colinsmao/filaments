"""Extract shared zero contours and populate explicit, evenly sampled curves."""
import numpy as np


def intersect_fields(a, b, axis_scale):
    """Intersect piecewise-linear A=0 and B=0 inside a tetrahedral grid.

    Shared triangular faces identify endpoints exactly, avoiding distance-based
    stitching that could accidentally join nearby independent strands.
    """
    n = a.shape[0]
    corners = np.array([[0, 0, 0], [0, 0, 1], [0, 1, 0], [0, 1, 1],
                        [1, 0, 0], [1, 0, 1], [1, 1, 0], [1, 1, 1]])
    av = np.stack([a[x:x+n-1, y:y+n-1, z:z+n-1] for x, y, z in corners], axis=-1)
    bv = np.stack([b[x:x+n-1, y:y+n-1, z:z+n-1] for x, y, z in corners], axis=-1)
    active = ((av.min(-1) <= 0) & (av.max(-1) >= 0)
              & (bv.min(-1) <= 0) & (bv.max(-1) >= 0))
    cells = np.argwhere(active)
    if not len(cells):
        return []
    av, bv = av[active], bv[active]
    # Consistent body diagonal and face diagonals in every cube.
    tetrahedra = ((0, 4, 6, 7), (0, 4, 5, 7), (0, 2, 6, 7),
                  (0, 2, 3, 7), (0, 1, 5, 7), (0, 1, 3, 7))
    faces = np.array(((0, 1, 2), (0, 1, 3), (0, 2, 3), (1, 2, 3)))
    endpoint_keys, endpoint_positions = [], []
    for tet in tetrahedra:
        triangle_corners = np.asarray(tet)[faces]
        va, vb = av[:, triangle_corners], bv[:, triangle_corners]
        weights = np.cross(va, vb)
        total = weights.sum(axis=-1)
        valid = np.abs(total) > 1e-15
        weights = weights / np.where(valid, total, 1)[..., None]
        valid &= (weights >= -1e-7).all(axis=-1) & (weights <= 1 + 1e-7).all(axis=-1)
        keep = np.count_nonzero(valid, axis=1) == 2
        if not keep.any():
            continue
        triangles = cells[keep, None, None, :] + corners[triangle_corners][None, :, :, :]
        ids = (triangles[..., 0] * n + triangles[..., 1]) * n + triangles[..., 2]
        endpoint_keys.append(np.sort(ids, axis=-1)[valid[keep]])
        pos = (triangles * weights[keep, ..., None]).sum(axis=-2)
        endpoint_positions.append(pos[valid[keep]])
    if not endpoint_keys:
        return []
    keys = np.concatenate(endpoint_keys)
    _, first, inverse = np.unique(keys, axis=0, return_index=True, return_inverse=True)
    vertices = (np.concatenate(endpoint_positions)[first] * (2 / (n - 1)) - 1) * axis_scale
    edges = inverse.reshape(-1, 2)
    adjacency = [[] for _ in vertices]
    for index, (i, j) in enumerate(edges):
        if i != j:
            adjacency[i].append((j, index))
            adjacency[j].append((i, index))
    visited = np.zeros(len(edges), dtype=bool)
    paths = []

    def trace(start, neighbor, edge):
        path = [start]
        while not visited[edge]:
            visited[edge] = True
            path.append(neighbor)
            if neighbor == start or len(adjacency[neighbor]) != 2:
                break
            choices = [(j, e) for j, e in adjacency[neighbor] if not visited[e]]
            if not choices:
                break
            neighbor, edge = choices[0]
        points = vertices[path]
        if len(points) >= 2:
            # Degenerate coincident endpoints can occur at exact grid zeros.
            keep = np.r_[True, np.linalg.norm(np.diff(points, axis=0), axis=1) > 1e-9]
            points = points[keep]
            if len(points) >= 2:
                paths.append(points)

    # Open curves first; remaining edges are closed loops.
    for i, neighbors in enumerate(adjacency):
        if len(neighbors) != 2:
            for j, edge in neighbors:
                if not visited[edge]:
                    trace(i, j, edge)
    for i, neighbors in enumerate(adjacency):
        for j, edge in neighbors:
            if not visited[edge]:
                trace(i, j, edge)
    return paths


def curve_length(points):
    return np.linalg.norm(np.diff(points, axis=0), axis=1).sum()


def resample(points, count):
    """Uniform arc-length samples, retaining endpoints and avoiding a duplicate loop seam."""
    distance = np.r_[0, np.cumsum(np.linalg.norm(np.diff(points, axis=0), axis=1))]
    closed = np.linalg.norm(points[0] - points[-1]) < 1e-8
    t = np.linspace(0, distance[-1], count, endpoint=not closed)
    if count == 1:
        t[:] = distance[-1] * 0.5
    return np.column_stack([np.interp(t, distance, points[:, axis]) for axis in range(3)])


def bundle(points, number, radius):
    """Coherent offset curves using a transported frame, not per-star scatter."""
    if number == 1 or radius == 0:
        return [points]
    closed = np.linalg.norm(points[0] - points[-1]) < 1e-8
    tangent = np.gradient(points, axis=0)
    if closed:
        tangent[0] = tangent[-1] = points[1] - points[-2]
    tangent /= np.maximum(np.linalg.norm(tangent, axis=1)[:, None], 1e-12)
    normal = np.empty_like(points)
    ref = np.eye(3)[np.argmin(np.abs(tangent[0]))]
    normal[0] = np.cross(tangent[0], ref)
    normal[0] /= np.linalg.norm(normal[0])
    for i in range(1, len(points)):
        v = np.cross(tangent[i-1], tangent[i])
        cosine = np.dot(tangent[i-1], tangent[i])
        rotated = normal[i-1] + np.cross(v, normal[i-1])
        rotated += np.cross(v, np.cross(v, normal[i-1])) / max(1 + cosine, 1e-8)
        rotated -= tangent[i] * np.dot(rotated, tangent[i])
        normal[i] = rotated / max(np.linalg.norm(rotated), 1e-12)
    binormal = np.cross(tangent, normal)
    if closed:
        # Distribute residual transport twist to close the bundle without a jump.
        angle = np.arctan2(np.dot(normal[0], binormal[-1]), np.dot(normal[0], normal[-1]))
        phase = np.linspace(0, angle, len(points))[:, None]
        normal = normal * np.cos(phase) + binormal * np.sin(phase)
        binormal = np.cross(tangent, normal)
    result = [points]
    for i in range(number - 1):
        angle = i * (np.pi * (3 - np.sqrt(5)))
        r = radius * np.sqrt((i + 1) / (number - 1))
        offset = points + r * (np.cos(angle) * normal + np.sin(angle) * binormal)
        if closed:
            offset[-1] = offset[0]
        result.append(offset)
    return result


def allocate_counts(lengths, count, minimum):
    """Reserve a floor per curve, then distribute the remaining budget by length.

    The caller orders curves by priority. If the budget cannot support all of
    them, retain a prefix. Counts below the minimum still return exactly count.
    """
    retained = min(len(lengths), max(1, count // minimum))
    lengths = np.asarray(lengths[:retained], dtype=float)
    if retained == 0:
        raise ValueError("No curves found; try a different seed, frequency or Y thickness")
    floor = min(minimum, count // retained)
    remaining = count - retained * floor
    ideal = remaining * lengths / lengths.sum()
    extra = np.floor(ideal).astype(int)
    order = np.argsort(-(ideal - extra), kind="stable")
    extra[order[:remaining - extra.sum()]] += 1
    return extra + floor
