"""Presentation metadata for central seed intervals and edge-fade intervals."""


def annotate_zones(parameters):
    entries = {p['key']: p for p in parameters}
    for key, label, kind in (
        ('seed_xz', 'XZ seed region', 'seed'),
        ('seed_y', 'Y seed region', 'seed'),
        ('fade_width', 'Edge fade starts', 'fade'),
        ('fade_xz_width', 'XZ fade starts', 'fade'),
        ('fade_y_width', 'Y fade starts', 'fade'),
    ):
        if key in entries:
            entries[key].update(zone_kind=kind, zone_label=label)
    for positive, negative, label, kind in (
        ('seed_y_pos', 'seed_y_neg', 'Y seed region', 'seed'),
        ('fade_y_pos_width', 'fade_y_neg_width', 'Y fade starts', 'fade'),
    ):
        if positive in entries and negative in entries:
            entries[positive].update(zone_kind=kind, zone_pair=negative, zone_label=label)
            entries[negative]['zone_hidden'] = True
    for entry in parameters:
        if 'zone_kind' in entry:
            extent = 'y_extent' if entry['key'].startswith(('seed_y', 'fade_y')) else 'extent'
            if extent in entries:
                entry['zone_extent'] = extent
    return parameters
