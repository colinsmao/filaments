"""Independent horizontal/vertical bounds and native density fading."""
import numpy as np
from _postprocess import edge_envelope, density_fade_weights, edge_dense_threshold


EXTENT_PARAMETERS = [
    dict(key='extent', label='XZ half-extent (units)', type='float', default=6., min=1., max=30.),
    dict(key='y_extent', label='Y half-extent (units)', type='float', default=6., min=0., max=30.),
]
FADE_PARAMETERS = []
for axis in ('xz', 'y'):
    group, toggle = f'{axis.upper()} edge fade', f'fade_{axis}'
    FADE_PARAMETERS.extend([
        dict(key=toggle, label=f'Fade {axis.upper()} edges', type='int', default=0,
             min=0, max=1, group=group, toggle=True),
        dict(key=f'{toggle}_width', label=f'{axis.upper()} fade width (fraction)', type='float',
             default=.8, min=.05, max=1., group=group, enabled_if=toggle),
        dict(key=f'{toggle}_density_strength', label=f'{axis.upper()} edge clump suppression', type='float',
             default=1., min=0., max=4., group=group, enabled_if=toggle),
    ])


def migrate_parameters(params):
    """Migrate old presets in the worker, without editing live settings files."""
    result = dict(params)
    result.setdefault('y_extent', result.get('extent', 6.) * result.get('y_scale', 1.))
    for axis in ('xz', 'y'):
        result.setdefault(f'fade_{axis}', result.get('fade', 0))
        result.setdefault(f'fade_{axis}_width', result.get('fade_width', .8))
        result.setdefault(f'fade_{axis}_density_strength', result.get('fade_density_strength', 1.))
    return result


def fade_density_axes(density, y_extent, fade_xz, fade_xz_width, fade_xz_density_strength,
                      fade_y, fade_y_width, fade_y_density_strength):
    if not fade_xz and (not fade_y or y_extent == 0):
        return density
    axis = np.abs(np.linspace(-1, 1, density.shape[0], dtype=np.float32))
    relative = density / edge_dense_threshold(density)
    weights = np.ones_like(density)
    if fade_xz:
        radius = np.maximum(axis[:, None, None], axis[None, None, :])
        weights = density_fade_weights(edge_envelope(radius, fade_xz_width), relative, fade_xz_density_strength)
    if fade_y and y_extent > 0:
        vertical = density_fade_weights(edge_envelope(axis[None, :, None], fade_y_width), relative,
                                       fade_y_density_strength)
        # Strongest attenuation wins; equal axis settings reproduce old box fade.
        weights = np.minimum(weights, vertical)
    return density * weights
