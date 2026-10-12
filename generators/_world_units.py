"""One-time preset migration; the active curve math then runs in blocks."""
DEFAULT_BLOCK_SCALE = 16.
NATIVE_GENERATOR = 'density_filament_curves'
NATIVE_CURVE_GENERATORS = {NATIVE_GENERATOR, 'density_filament_branching'}
LENGTH_KEYS = {
    'extent', 'y_extent', 'noise_scale', 'seed_spacing', 'strand_length',
    'pop_spread_xz', 'pop_spread_y', 'pop_clump_scale', 'pop_size',
    'pp_curve_reach', 'pp_curve_length', 'pp_merge_distance',
    'pp_swirl_radius', 'pp_warp_amount', 'pp_warp_scale',
    'star_size', 'pp_density_radius',
}


def block_schema(parameters):
    result = []
    for original in parameters:
        entry = dict(original)
        key = entry['key']
        if key == 'pop_block_scale':
            entry.update(key='pop_blocks', label='Block population', type='int',
                         default=1, min=0, max=1, toggle=True)
        elif key in LENGTH_KEYS:
            entry['default'] *= DEFAULT_BLOCK_SCALE
            # Cover all previously supported scales without clamping old presets.
            entry['max'] *= 128
            entry['label'] = entry['label'].replace('units', 'blocks')
        elif key == 'pop_density':
            entry['default'] /= DEFAULT_BLOCK_SCALE
            entry['label'] = 'Stars per block of curve'
        if entry.get('enabled_if') == 'pop_block_scale':
            entry['enabled_if'] = 'pop_blocks'
        result.append(entry)
    return result


def migrate_to_blocks(supplied, legacy_schema, direct_scale=None):
    if supplied.get('_block_units') == 1:
        return dict(supplied)
    # Presets first receive historical defaults, so omitted lengths/densities
    # migrate consistently. Fresh block presets enter with scale 16 explicitly.
    values = {e['key']: e['default'] for e in legacy_schema}
    values.update(supplied)
    scale = max(1., min(128., float(values.get('pop_block_scale', 0))))
    if direct_scale is not None:
        scale = direct_scale
        values['noise_scale'] = values['extent'] / values.get('frequency', 2.)
    elif not values.get('pop_block_scale', 0):
        scale = DEFAULT_BLOCK_SCALE
    for key in LENGTH_KEYS:
        if key in values:
            values[key] *= scale
    if 'pop_density' in values:
        values['pop_density'] /= scale
        values['pop_blocks'] = int(bool(values.pop('pop_block_scale', 0)))
    values['_block_units'] = 1
    return values
