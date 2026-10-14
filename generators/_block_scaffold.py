"""Unguided growth of a face-connected block graph. No population or field input."""
from dataclasses import dataclass
from collections import Counter
from math import gcd
import numpy as np


STEPS = np.asarray([(1, 0, 0), (-1, 0, 0), (0, 1, 0),
                    (0, -1, 0), (0, 0, 1), (0, 0, -1)], dtype=np.int32)
# Integer slopes describe the proportions of face steps in a run. They never
# produce continuous positions or rounded continuous trajectories.
HEADINGS = np.asarray([(x, y, z) for x in range(-3, 4) for y in range(-3, 4)
                       for z in range(-3, 4) if gcd(gcd(abs(x), abs(y)), abs(z)) == 1], float)
UNITS = HEADINGS / np.linalg.norm(HEADINGS, axis=1)[:, None]


@dataclass
class Scaffold:
    cells: np.ndarray
    edges: np.ndarray
    paths: list
    parents: np.ndarray
    roots: np.ndarray
    owners: np.ndarray
    cell_paths: np.ndarray
    stops: list
    stats: dict


def _near_in_graph(adjacency, start, targets, limit):
    """Whether an extra physical contact would make a cycle shorter than limit."""
    targets = set(targets)
    frontier, seen = [start], {start}
    for _ in range(limit):
        if any(i in targets for i in frontier):
            return True
        frontier = list({j for i in frontier for j in adjacency[i] if j not in seen})
        seen.update(frontier)
        if not frontier:
            return False
    return False


def grow(seed, width=275, height=55, root_count=24,
         cells_per_root=600, trunk_length=120, run_length=8, turn_angle=50.,
         branch_spacing=12, child_fraction=.65, vertical_motion=.35, allow_joins=1,
         axis_run=2, bend_memory=0., child_length_cap=0,
         branch_active_length=0, branch_quiet_length=0):
    """Return an explicit integer-cell graph and its parent/child paths.

    roots launch two opposed trunks. Each tip has a finite path lifetime; child
    lifetimes scale with their parent's ORIGINAL lifetime. All descendants spend
    the same finite root cell allowance. Round-robin growth avoids exhausting that
    allowance on one depth-first branch. The allowance is a cap, not a fill quota.

    Runs are digital lines made by accumulating integer-slope step deficits.
    Heading changes are local random events, not samples of a spatial field.
    If the preferred staircase step is blocked, try the other signed face steps
    of that same heading. This changes the lattice ordering, not the heading.
    Vertical motion weights the distribution of headings; it is not Y scaling.
    Axis runs hold a chosen face axis for a geometric number of steps (requested
    mean axis_run), subject to turns, launch steps and contacts. Deficits accumulate
    during a hold, preserving the heading's long-run proportions. One recovers
    the original single-step scheduler and random streams exactly.
    Optional bend memory biases each new turn toward continuation of the previous
    turn plane. It only changes probabilities of integer slopes; positions remain
    face steps. Zero preserves the previous implementation and random streams.
    A nonzero child_length_cap bounds child lifetime independently of trunk reach.
    Optional alternating active/quiet branching periods are local tip state, not
    a preselected patch layout. The old rule is exact when either period is zero.
    Every non-parent face contact is either recorded as a join or refused. Short
    graph cycles (< 10 edges) are refused to avoid immediate self/parent hugging.
    """
    width, height, root_count = int(width), int(height), int(root_count)
    cells_per_root, trunk_length = int(cells_per_root), int(trunk_length)
    if not (8 <= width <= 512 and 4 <= height <= 256 and 1 <= root_count <= 64):
        raise ValueError('Invalid scaffold domain or root count')
    if not (8 <= cells_per_root <= 5000 and 8 <= trunk_length <= 512):
        raise ValueError('Invalid scaffold cell allowance or trunk length')
    if root_count * cells_per_root > 40000:
        raise ValueError('Scaffold allowance exceeds 40,000 cells; reduce roots or cells per root')
    if int(axis_run) != axis_run or not 1 <= axis_run <= 8:
        raise ValueError('Axis run must be an integer from 1 to 8')
    axis_run = int(axis_run)
    if not 0. <= bend_memory <= 1.:
        raise ValueError('Bend memory must be between 0 and 1')
    if any(int(v) != v or not 0 <= v <= 512 for v in
           (child_length_cap, branch_active_length, branch_quiet_length)):
        raise ValueError('Branch lengths must be integers from 0 to 512')
    burst_branching = bool(branch_active_length and branch_quiet_length)
    if not (2 <= run_length <= 32 and 5 <= turn_angle <= 100 and 3 <= branch_spacing <= 64
            and .2 <= child_fraction <= .9 and .05 <= vertical_motion <= 1):
        raise ValueError('Invalid local growth parameters')
    lo = -np.asarray([width // 2, height // 2, width // 2])
    hi = lo + np.asarray([width, height, width])
    rng = np.random.default_rng(np.random.SeedSequence([int(seed), 79013]))
    vertical_weights = np.exp(-.5 * (UNITS[:, 1] / vertical_motion) ** 2)
    cells, owners, cell_paths, adjacency, edge_set = [], [], [], [], set()
    lookup, paths, parents, root_nodes, tips, stops = {}, [], [], [], [], []
    used = np.zeros(root_count, dtype=int)
    event_counts = Counter()

    def add_cell(cell, owner, path):
        i = len(cells)
        cells.append(tuple(int(v) for v in cell))
        lookup[cells[-1]] = i
        owners.append(owner)
        cell_paths.append(path)
        adjacency.append(set())
        used[owner] += 1
        return i

    def edge(a, b):
        edge_set.add((min(a, b), max(a, b)))
        adjacency[a].add(b)
        adjacency[b].add(a)

    def heading(local, old=None, branch=False, bend=None):
        weights = vertical_weights.copy()
        if old is not None:
            dot = UNITS @ (old / np.linalg.norm(old))
            low, high = (55., 110.) if branch else (max(5., turn_angle * .45), turn_angle)
            weights *= (dot <= np.cos(np.deg2rad(low))) & (dot >= np.cos(np.deg2rad(high)))
            if bend_memory and bend is not None and not branch:
                # Each candidate's turn direction lies perpendicular to old.
                # The remembered tangent is transported by the previous turn.
                tangent = UNITS - dot[:, None] * (old / np.linalg.norm(old))
                tangent /= np.maximum(np.linalg.norm(tangent, axis=1)[:, None], 1e-12)
                weights *= np.exp(8. * bend_memory * (tangent @ bend))
        if weights.sum() == 0:
            return old.copy()  # No different integer slope fits a very small cone.
        weights /= weights.sum()
        return HEADINGS[local.choice(len(HEADINGS), p=weights)].copy()

    def interval(local, mean):
        return int(local.integers(max(2, int(mean * .5)), max(3, int(mean * 1.5) + 1)))

    def add_tip(node, direction, life, owner, parent=-1, launch_axis=-1):
        pid = len(paths)
        local = np.random.default_rng(np.random.SeedSequence([int(seed), 1831, owner, pid]))
        paths.append([node])
        parents.append(parent)
        stops.append('active')
        tips.append(dict(pid=pid, owner=owner, node=node, direction=direction,
                         debt=np.zeros(3), life=life, original_life=life, traveled=0,
                         run=interval(local, run_length), fork=interval(local, branch_spacing),
                         local=local, launch_axis=launch_axis,
                         axis_local=np.random.default_rng(np.random.SeedSequence([int(seed), 76103, owner, pid])),
                         held_axis=-1, held_left=0, bend=None,
                         launch_left=int(local.integers(2, 4)) if launch_axis >= 0 else 0))
        if burst_branching:
            branch_rng = np.random.default_rng(np.random.SeedSequence([int(seed), 88519, owner, pid]))
            tips[-1].update(branch_rng=branch_rng, branch_active=True,
                            branch_until=interval(branch_rng, branch_active_length))
        return tips[-1]

    # Birth locations are uniform in an inner box, with only a two-cell exclusion.
    # One-root patches start at the origin for easy local inspection.
    for owner in range(root_count):
        for attempt in range(1000):
            cell = np.zeros(3, dtype=int) if root_count == 1 else rng.integers(
                np.ceil(lo * .7).astype(int), np.floor((hi - 1) * .7).astype(int) + 1)
            if all(np.max(np.abs(cell - np.asarray(other))) > 2 for other in cells):
                break
        else:
            raise ValueError('Cannot place separated roots in this domain')
        node = add_cell(cell, owner, len(paths))
        root_nodes.append(node)
        direction = heading(rng)
        length = max(4, int(round(trunk_length * rng.uniform(.7, 1.3) / 2)))
        add_tip(node, direction, length, owner)
        add_tip(node, -direction, length, owner)

    active = list(tips)
    while active:
        survivors, children = [], []
        for tip in active:
            pid, owner, p = tip['pid'], tip['owner'], tip['node']
            local, direction = tip['local'], tip['direction']
            if used[owner] >= cells_per_root:
                stops[pid] = 'cell_cap'
                continue
            if tip['life'] <= 0:
                stops[pid] = 'lifetime'
                continue
            if tip['run'] <= 0 and not tip['launch_left']:
                previous = direction / np.linalg.norm(direction)
                direction = heading(local, direction, bend=tip['bend'])
                if bend_memory:
                    current = direction / np.linalg.norm(direction)
                    # Derivative of the same spherical bend at its new heading.
                    tangent = current * np.dot(previous, current) - previous
                    length = np.linalg.norm(tangent)
                    if length > 1e-10:
                        tip['bend'] = tangent / length
                tip.update(direction=direction, run=interval(local, run_length), debt=np.zeros(3), held_left=0)
            tip['debt'] += np.abs(direction) / np.abs(direction).sum()
            axes = [tip['launch_axis']] if tip['launch_left'] else [
                int(a) for a in np.argsort(-tip['debt'], kind='stable') if direction[a] != 0]
            if axis_run > 1 and not tip['launch_left']:
                if not tip['held_left']:
                    tip['held_axis'] = axes[0]
                    tip['held_left'] = int(tip['axis_local'].geometric(1. / axis_run))
                axes = [tip['held_axis']] + [a for a in axes if a != tip['held_axis']]
            refused = []
            for axis in axes:
                offset = np.zeros(3, dtype=int)
                offset[axis] = 1 if direction[axis] > 0 else -1
                q = np.asarray(cells[p]) + offset
                if np.any(q < lo) or np.any(q >= hi):
                    refused.append('boundary')
                    continue
                occupied = lookup.get(tuple(q))
                if occupied is not None:
                    if not allow_joins or _near_in_graph(adjacency, p, [occupied], 9):
                        refused.append('blocked_contact')
                        continue
                    contacts = []
                    break
                contacts = [lookup[tuple(q + d)] for d in STEPS
                            if tuple(q + d) in lookup and lookup[tuple(q + d)] != p]
                # Every face touching another scaffold cell is physical adjacency.
                # Refuse a move that would create an unrecorded or very short loop.
                anchors = [p] + contacts
                if contacts and (not allow_joins or any(
                        _near_in_graph(adjacency, a, anchors[i + 1:], 8)
                        for i, a in enumerate(anchors[:-1]))):
                    refused.append('blocked_contact')
                    continue
                break
            else:
                stops[pid] = 'boundary' if all(r == 'boundary' for r in refused) else 'blocked_contact'
                continue
            if refused:
                event_counts['alternate_steps'] += 1
            if not tip['launch_left'] and tip['held_left']:
                tip['held_left'] = tip['held_left'] - 1 if axis == tip['held_axis'] else 0
            tip['debt'][axis] -= 1
            if occupied is not None:
                edge(p, occupied)
                paths[pid].append(occupied)
                stops[pid] = 'join'
                event_counts['joins'] += 1
                continue
            node = add_cell(q, owner, pid)
            edge(p, node)
            for contact in contacts:
                edge(node, contact)
            paths[pid].append(node)
            tip.update(node=node, life=tip['life'] - 1, traveled=tip['traveled'] + 1,
                       run=tip['run'] - 1, launch_left=max(0, tip['launch_left'] - 1))
            if contacts:
                stops[pid] = 'join'
                event_counts['joins'] += 1
                continue
            branch_active = True
            if burst_branching:
                if tip['traveled'] >= tip['branch_until']:
                    tip['branch_active'] = not tip['branch_active']
                    span = branch_active_length if tip['branch_active'] else branch_quiet_length
                    tip['branch_until'] = tip['traveled'] + interval(tip['branch_rng'], span)
                    if tip['branch_active']:
                        tip['fork'] = tip['traveled'] + interval(local, branch_spacing)
                branch_active = tip['branch_active']
            if branch_active and tip['traveled'] >= tip['fork'] and tip['life'] >= 3:
                tip['fork'] = tip['traveled'] + interval(local, branch_spacing)
                child_life = int(tip['original_life'] * child_fraction * local.uniform(.65, 1.25))
                if child_length_cap:
                    child_life = min(child_life, int(child_length_cap))
                if child_life >= 5:
                    for _ in range(12):
                        child_direction = heading(local, direction, branch=True)
                        # A short face-axis departure separates forks on the grid.
                        # Probe only actual nearby cells; there is no destination.
                        launch_axis = int(np.argmax(np.abs(child_direction)))
                        child_step = np.zeros(3, dtype=int)
                        child_step[launch_axis] = 1 if child_direction[launch_axis] > 0 else -1
                        probe = q + child_step
                        if np.any(probe < lo) or np.any(probe >= hi):
                            continue
                        if any(tuple(probe + d) in lookup and lookup[tuple(probe + d)] != node
                               for d in STEPS) or tuple(probe) in lookup:
                            continue
                        children.append(add_tip(node, child_direction, child_life, owner, pid, launch_axis))
                        break
            survivors.append(tip)
        active = survivors + children

    # Failed branch attempts are retained as explicit diagnostics but are not
    # counted as actual forks. They never add isolated cells.
    components = 0
    seen = set()
    for i in range(len(cells)):
        if i in seen:
            continue
        components += 1
        stack = [i]
        seen.add(i)
        while stack:
            for j in adjacency[stack.pop()]:
                if j not in seen:
                    seen.add(j)
                    stack.append(j)
    degrees = np.asarray([len(a) for a in adjacency])
    stats = dict(cells=len(cells), edges=len(edge_set), components=components,
                 cycles=len(edge_set) - len(cells) + components,
                 forks=int((degrees >= 3).sum()), endpoints=int((degrees == 1).sum()),
                 paths=sum(len(p) > 1 for p in paths), empty_paths=sum(len(p) == 1 for p in paths),
                 joins=event_counts['joins'], alternate_steps=event_counts['alternate_steps'], cells_by_root=used.tolist(),
                 stops=dict(Counter(stops)), bounds=np.ptp(np.asarray(cells), axis=0).tolist())
    return Scaffold(np.asarray(cells, dtype=np.int32), np.asarray(sorted(edge_set), dtype=np.int32).reshape(-1, 2),
                    [np.asarray(p, dtype=np.int32) for p in paths], np.asarray(parents, dtype=np.int32),
                    np.asarray(root_nodes, dtype=np.int32), np.asarray(owners, dtype=np.int32),
                    np.asarray(cell_paths, dtype=np.int32), stops, stats)


def cell_colors(scaffold, by_branch=True):
    ids = scaffold.cell_paths if by_branch else scaffold.owners
    return (.58 + .32 * np.cos(ids[:, None] * 2.399963 + np.asarray([0., 2.0944, 4.1888]))).astype(np.float32)


def preview(scaffold, blocks=False, by_branch=True, mark_junctions=True):
    """Line-only viewer output. Blocks are diagnostic wire cells, never stars."""
    centers = scaffold.cells.astype(np.float32) + .5
    colors = cell_colors(scaffold, by_branch)
    if mark_junctions:
        degree = np.bincount(scaffold.edges.ravel(), minlength=len(centers))
        colors[degree >= 3] = [1., .9, .35]
        colors[scaffold.roots] = [1., .25, .35]
    if blocks:
        corners = np.asarray([(x, y, z) for x in (0., 1.) for y in (0., 1.) for z in (0., 1.)], np.float32)
        edge_ids = [(a, b) for a in range(8) for b in range(a + 1, 8)
                    if np.abs(corners[a] - corners[b]).sum() == 1]
        offsets = corners[np.asarray(edge_ids)].reshape(-1, 3)
        vertices = (scaffold.cells[:, None, :] + offsets).reshape(-1, 3).astype(np.float32)
        rgb = np.repeat(colors, 24, axis=0)
    else:
        vertices = centers[scaffold.edges].reshape(-1, 3)
        rgb = colors[scaffold.edges].reshape(-1, 3)
    return vertices, rgb, np.full(len(vertices), .04, dtype=np.float32)
