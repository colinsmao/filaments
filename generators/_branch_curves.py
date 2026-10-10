"""A graph induced only by intersections of piecewise-linear noise surfaces."""
from itertools import combinations
import numpy as np


def intersection_graph(fields, extent=1.):
    """Split every pairwise zero segment at its shared triple-zero junctions.

    A consistent tetrahedral mesh defines the scalar-field interpolation. Face
    vertices are identified by (field pair, triangular face), junctions by
    (field triple, tetrahedron). No proximity-based connections are introduced.
    """
    fields = np.asarray(fields, dtype=float)
    number, n = fields.shape[:2]
    pairs = list(combinations(range(number), 2))
    triples = list(combinations(range(number), 3))
    corners = np.array([[0, 0, 0], [0, 0, 1], [0, 1, 0], [0, 1, 1],
                        [1, 0, 0], [1, 0, 1], [1, 1, 0], [1, 1, 1]])
    values = np.stack([fields[:, x:x+n-1, y:y+n-1, z:z+n-1]
                       for x, y, z in corners], axis=-1)
    crossings = (values.min(-1) <= 0) & (values.max(-1) >= 0)
    active = crossings.sum(axis=0) >= 2
    cells = np.argwhere(active)
    values = values[:, active].transpose(1, 2, 0)
    tetrahedra = ((0, 4, 6, 7), (0, 4, 5, 7), (0, 2, 6, 7),
                  (0, 2, 3, 7), (0, 1, 3, 7), (0, 1, 5, 7))
    faces = np.array(((0, 1, 2), (0, 1, 3), (0, 2, 3), (1, 2, 3)))
    all_keys, all_positions, all_families = [], [], []
    for tet in tetrahedra:
        positions = cells[:, None, :] + corners[list(tet)][None]
        ids = (positions[..., 0] * n + positions[..., 1]) * n + positions[..., 2]
        tv = values[:, list(tet)]
        junctions = {}
        for triple in triples:
            matrix = np.concatenate((np.ones((len(cells), 1, 4)), tv[:, :, triple].transpose(0, 2, 1)), axis=1)
            valid = np.abs(np.linalg.det(matrix)) > 1e-12
            weights = np.zeros((len(cells), 4))
            weights[valid] = np.linalg.solve(matrix[valid], np.broadcast_to([1., 0., 0., 0.], (valid.sum(), 4)))
            valid &= (weights >= -1e-9).all(axis=1) & (weights <= 1 + 1e-9).all(axis=1)
            keys = np.empty((len(cells), 8), dtype=np.int64)
            keys[:, :4] = (1, *triple)
            keys[:, 4:] = np.sort(ids, axis=1)
            junctions[triple] = ((weights[..., None] * positions).sum(axis=1), keys, valid)

        for family, (a, b) in enumerate(pairs):
            weights = np.cross(tv[:, faces, a], tv[:, faces, b])
            total = weights.sum(axis=-1)
            valid = np.abs(total) > 1e-12
            weights /= np.where(valid, total, 1)[..., None]
            valid &= (weights >= -1e-9).all(axis=-1) & (weights <= 1 + 1e-9).all(axis=-1)
            keep = valid.sum(axis=1) == 2
            if not keep.any():
                continue
            face_pos = (positions[:, faces] * weights[..., None]).sum(axis=2)
            endpoints = face_pos[keep][valid[keep]].reshape(-1, 2, 3)
            face_ids = np.sort(ids[:, faces], axis=-1)[keep][valid[keep]].reshape(-1, 2, 3)
            keys = np.full((len(endpoints), 2, 8), -1, dtype=np.int64)
            keys[:, :, :3] = (0, a, b)
            keys[:, :, 4:7] = face_ids
            candidate_pos, candidate_keys = [endpoints], [keys]
            parameters = [np.broadcast_to([0., 1.], (len(endpoints), 2))]
            delta = endpoints[:, 1] - endpoints[:, 0]
            norm2 = np.maximum((delta * delta).sum(axis=1), 1e-24)
            for triple, (jp, jk, jv) in junctions.items():
                if a not in triple or b not in triple:
                    continue
                t = ((jp[keep] - endpoints[:, 0]) * delta).sum(axis=1) / norm2
                t = np.where(jv[keep], np.clip(t, 0, 1), np.inf)
                candidate_pos.append(jp[keep, None])
                candidate_keys.append(jk[keep, None])
                parameters.append(t[:, None])
            ts = np.concatenate(parameters, axis=1)
            order = np.argsort(ts, axis=1, kind="stable")
            cp = np.take_along_axis(np.concatenate(candidate_pos, axis=1), order[..., None], axis=1)
            ck = np.take_along_axis(np.concatenate(candidate_keys, axis=1), order[..., None], axis=1)
            ts = np.take_along_axis(ts, order, axis=1)
            for slot in range(cp.shape[1] - 1):
                use = np.isfinite(ts[:, slot + 1]) & (ts[:, slot + 1] > ts[:, slot] + 1e-10)
                all_positions.append(cp[use, slot:slot+2].reshape(-1, 3))
                all_keys.append(ck[use, slot:slot+2].reshape(-1, 8))
                all_families.append(np.full(use.sum(), family, dtype=np.int32))
    if not all_keys or not any(len(k) for k in all_keys):
        raise ValueError("No zero-intersection curves found; try another seed or noise scale")
    keys, first, inverse = np.unique(np.concatenate(all_keys), axis=0, return_index=True, return_inverse=True)
    vertices = (np.concatenate(all_positions)[first] * (2. / (n - 1)) - 1) * extent
    return vertices, inverse.reshape(-1, 2), np.concatenate(all_families), keys[:, 0] == 1


def trace_graph(graph, seed, seed_count=4, length=15., branch_probability=.5, max_paths=96):
    """Grow along noise-induced edges; branches can only start at true junctions."""
    vertices, edges, families, junctions = graph
    adjacency = [[] for _ in vertices]
    for edge, (a, b) in enumerate(edges):
        adjacency[a].append(edge)
        adjacency[b].append(edge)
    # Prefer A/B triple-zero junctions as roots, then ordinary A/B vertices.
    ab_nodes = np.unique(edges[families == 0])
    candidates = ab_nodes[junctions[ab_nodes]]
    if not len(candidates):
        candidates = ab_nodes
    if not len(candidates):
        raise ValueError("No A/B roots found; try another seed or noise scale")
    rng = np.random.default_rng(np.random.SeedSequence([seed, 5123]))
    chosen = [int(rng.choice(candidates))]
    distances = np.full(len(candidates), np.inf)
    for _ in range(min(int(seed_count), len(candidates)) - 1):
        distances = np.minimum(distances, np.linalg.norm(vertices[candidates] - vertices[chosen[-1]], axis=1))
        distances[np.isin(candidates, chosen)] = -1
        chosen.append(int(candidates[np.argmax(distances)]))
    # Per-node/family choices are stable when branch probability changes.
    decisions = np.random.default_rng(np.random.SeedSequence([seed, 9173])).random((len(vertices), 6))
    queue = [(node, edge, float(length)) for node in chosen for edge in adjacency[node] if families[edge] == 0]
    # A root on a triple zero is already an eligible branching encounter.
    for node in chosen:
        for family in sorted({int(families[e]) for e in adjacency[node]} - {0}):
            if decisions[node, family] < branch_probability:
                choices = [e for e in adjacency[node] if families[e] == family]
                queue.append((node, choices[0], float(length)))
    visited = np.zeros(len(edges), dtype=bool)
    paths, path_families = [], []
    used_junctions = {node for node in chosen if junctions[node]}
    for start, first_edge, budget in queue:
        if len(paths) >= max_paths:
            break
        if visited[first_edge]:
            continue
        node, edge, family = start, first_edge, families[first_edge]
        path = [vertices[node]]
        while not visited[edge]:
            target = int(edges[edge, 1] if edges[edge, 0] == node else edges[edge, 0])
            distance = np.linalg.norm(vertices[target] - vertices[node])
            if distance > budget:
                path.append(vertices[node] + (vertices[target] - vertices[node]) * budget / distance)
                break
            visited[edge] = True
            path.append(vertices[target])
            budget -= distance
            incoming = vertices[target] - vertices[node]
            node = target
            if junctions[node]:
                used_junctions.add(node)
                options = {}
                for candidate in adjacency[node]:
                    if not visited[candidate] and families[candidate] != family:
                        options.setdefault(int(families[candidate]), []).append(candidate)
                for other, choices in sorted(options.items()):
                    if decisions[node, other] < branch_probability and budget > .01 and len(queue) < max_paths * 4:
                        # One direction per new pair, favoring forward continuation.
                        def alignment(candidate):
                            a, b = edges[candidate]
                            outgoing = vertices[b if a == node else a] - vertices[node]
                            return np.dot(outgoing, incoming) / max(np.linalg.norm(outgoing), 1e-12)
                        queue.append((node, max(choices, key=alignment), budget))
            continuation = [e for e in adjacency[node] if not visited[e] and families[e] == family]
            if not continuation or budget <= 1e-9:
                break
            edge = continuation[0]
        if len(path) > 1:
            paths.append(np.asarray(path))
            path_families.append(family)
    return paths, np.asarray(path_families), vertices[chosen], vertices[sorted(used_junctions)]
