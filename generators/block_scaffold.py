"""Scaffold-only experiment: no density, guidance field or star population."""
from _block_scaffold import grow, preview

NAME = 'Unguided block scaffold (no stars)'
PRIMITIVE = 'lines'
NATIVE_BLOCKS = True


def control(key, label, kind, default, lo, hi, description, group='Local growth', **hints):
    return dict(key=key, label=label, type=kind, default=default, min=lo, max=hi,
                description=description, group=group, **hints)


PARAMETERS = [
    control('width', 'XZ size (blocks)', 'int', 275, 8, 512,
            'Full width and depth of the block domain. Outside steps are refused; changes geometry and cell count.', 'Domain'),
    control('height', 'Y size (blocks)', 'int', 55, 4, 256,
            'Full height in blocks. No post-growth compression. Changes geometry and cell count.', 'Domain'),
    control('root_count', 'Roots', 'int', 24, 1, 64,
            'Uniform random roots in the inner 70% of each axis, with local separation. One root starts at center. More roots usually add cells.', 'Domain'),
    control('cells_per_root', 'Cell cap per root', 'int', 600, 8, 5000,
            'Maximum distinct scaffold cells shared by a root and all its branches. A cap, not a target. Total allowed cells must be <= 40000.'),
    control('trunk_length', 'Mean two-way trunk length (steps)', 'int', 120, 8, 512,
            'Total nominal face steps in both root directions; each root varies by 0.7-1.3. Larger permits longer trunks and descendants; cell count can rise.'),
    control('run_length', 'Mean heading run (steps)', 'int', 8, 2, 32,
            'Face steps between random heading changes, drawn from 0.5-1.5 times this value. Larger gives longer consistent runs; changes cell count through contacts.'),
    control('axis_run', 'Mean axis run (blocks)', 'int', 2, 1, 8,
            'Requested consecutive face steps on a chosen axis, drawn geometrically with this mean. Turns or blocked steps can shorten a run. Two keeps half the requested runs at one block, with occasional longer runs. One restores the original scheduler exactly. Changes scaffold geometry and cell count; no stars.'),
    control('turn_angle', 'Maximum heading turn (degrees)', 'float', 50., 5., 100.,
            'New integer slope is drawn between 45% and 100% of this angle from the previous heading. Larger bends more; may change cell count.'),
    control('branch_spacing', 'Mean fork opportunity gap (steps)', 'int', 12, 3, 64,
            'Draw 0.5-1.5 times this many face steps between local branch attempts. Smaller creates more opportunities; may add cells up to the shared cap.'),
    control('child_fraction', 'Child lifetime fraction', 'float', .65, .2, .9,
            'Child lifetime / parent initial lifetime, multiplied by a draw from 0.65-1.25. Fractions below 0.8 always shorten descendants. Changes cell count.'),
    control('vertical_motion', 'Vertical direction weight', 'float', .35, .05, 1.,
            'Local heading weight exp(-0.5*(unit_heading_Y/value)^2). Higher allows steeper paths. No spatial field or coordinate scaling; changes cell count.'),
    control('allow_joins', 'Allow local contacts', 'int', 1, 0, 1,
            'On: record actual face contacts, then stop that tip. Off: stop before touching. Very short loops are refused in both modes. Changes geometry and count.', toggle=True),
    control('preview_blocks', 'Wire block cells', 'int', 0, 0, 1,
            'Show wire unit cells instead of graph links. Diagnostic geometry only; growth is unchanged.', 'Preview', toggle=True),
    control('color_branches', 'Color individual branches', 'int', 1, 0, 1,
            'On: per-path colors. Off: per-root colors. No geometry or count change.', 'Preview', toggle=True),
    control('mark_junctions', 'Mark roots / junctions', 'int', 1, 0, 1,
            'Red root cells; yellow cells with at least three graph neighbors. No geometry or count change.', 'Preview', toggle=True),
]


def generate(count, seed, preview_blocks=0, color_branches=1, mark_junctions=1, **params):
    graph = grow(seed, **params)
    return preview(graph, bool(preview_blocks), bool(color_branches), bool(mark_junctions))
