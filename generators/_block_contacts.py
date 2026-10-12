"""Incremental unit-cell contacts with exact segment attachments; no forces."""
import math


def crossed_cells(start, end):
    """Yield (cell, entry, exit) in travel order for a segment's positive-length spans.

    Cells are half-open. Simultaneous boundary crossings advance all tied axes;
    cells touched only at an edge/corner are not occupied. Negative travel from
    an exact integer starts in the cell on that side of the boundary.
    """
    delta = tuple(b-a for a, b in zip(start, end))
    if not any(delta):
        return
    cell = [math.floor(a)-(int(a == math.floor(a)) if d < 0 else 0)
            for a, d in zip(start, delta)]
    direction = [1 if d > 0 else -1 if d < 0 else 0 for d in delta]
    stride = [abs(1/d) if d else math.inf for d in delta]
    boundary = [((c+1-a)/d if d > 0 else (c-a)/d) if d else math.inf
                for c, a, d in zip(cell, start, delta)]
    entry = 0.
    while entry < 1.:
        leave = min(1., *boundary)
        if leave > entry:
            yield tuple(cell), entry, leave
        if leave >= 1.:
            break
        for axis in range(3):
            if boundary[axis] <= leave+1e-12:
                cell[axis] += direction[axis]
                boundary[axis] += stride[axis]
        entry = leave


class BlockContacts:
    """Store every deposited segment span, including differently oriented crossings.

    Call advance in stable tip order within each simultaneous growth step. New
    proposals can attach only to geometry already accepted, never speculative
    segments which could subsequently disappear. Both halves share one owner.
    """
    def __init__(self, angle=30.):
        self.cosine = math.cos(math.radians(angle))
        self.cells = {}
        self.joins = 0

    def advance(self, start, end, owner, budget):
        start, end = tuple(map(float, start)), tuple(map(float, end))
        delta = tuple(b-a for a, b in zip(start, end))
        length = math.sqrt(sum(d*d for d in delta))
        if length <= 1e-10:
            return end, False
        tangent = tuple(d/length for d in delta)
        spans = list(crossed_cells(start, end))
        contact = None
        for cell, entry, leave in spans:
            candidates = self.cells.get(cell)
            if candidates is None:
                continue
            # Attach to the closest eligible target piece at this cell entry.
            # The stored piece is clipped to this block, so attachment cannot
            # jump to a distant part of a long target segment.
            point = tuple(a+entry*d for a, d in zip(start, delta))
            nearest = math.inf
            for segment, lower, upper in candidates:
                other, origin, vector, axis, norm2 = segment
                if other == owner or abs(sum(a*b for a, b in zip(tangent, axis)))+1e-12 < self.cosine:
                    continue
                fraction = min(upper, max(lower, sum((a-b)*d for a, b, d in zip(point, origin, vector))/norm2))
                target = tuple(a+fraction*d for a, d in zip(origin, vector))
                distance = sum((a-b)**2 for a, b in zip(point, target))
                travel2 = sum((a-b)**2 for a, b in zip(start, target))
                if distance < nearest and travel2 <= (budget+1e-9)**2:
                    nearest, contact = distance, target
            if contact is not None:
                break
        if contact is not None:
            end = contact
            delta = tuple(b-a for a, b in zip(start, end))
            length = math.sqrt(sum(d*d for d in delta))
            self.joins += 1
            if length <= 1e-10:
                return end, True
            tangent = tuple(d/length for d in delta)
            spans = list(crossed_cells(start, end))
        segment = owner, start, delta, tangent, length*length
        for cell, entry, leave in spans:
            # Share segment geometry across cells; only clipping parameters
            # belong to each occupancy record. No per-cell vector allocations.
            self.cells.setdefault(cell, []).append((segment, entry, leave))
        return end, contact is not None
