"""Optional persistent identities for a selected subset of population paths."""
import numpy as np


def curve_ids(params, count):
    ids = np.asarray(params.get('_curve_ids', np.arange(count)))
    if ids.shape != (count,) or ids.dtype.kind not in 'iu' or (ids < 0).any():
        raise ValueError('Population identities must be one nonnegative integer per curve')
    return ids
