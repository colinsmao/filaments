"""One-shot, renderer-independent generation protocol. No OpenGL imports."""
import argparse
import json
import math
from pathlib import Path
import struct
import sys
import time
import traceback
import types

MAX_POINTS = 1_000_000

# Bundled shared processors are available even for external generator folders.
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "generators"))
from _postprocess import FADE_PARAMETER, FADE_WIDTH_PARAMETER, FADE_DENSITY_PARAMETER, APPEARANCE_PARAMETERS, apply_to_stars
from _population import PARAMETERS as POPULATION_PARAMETERS, FIELD_PARAMETER, populate_curves, migrate_parameters as migrate_population
from _block_lighting import PARAMETERS as LIGHTING_PARAMETERS, apply_lighting, migrate_parameters as migrate_lighting
from _world_units import NATIVE_GENERATOR, NATIVE_CURVE_GENERATORS, block_schema, migrate_to_blocks
from _density_field import PARAMETERS as FIELD_PARAMETERS, KEYS as FIELD_KEYS


def load_catalog(directory, block_units=False, density_graph=False):
    catalog, modules, errors = [], {}, []
    # Keep compiled dependencies available when generators are copied or overridden.
    local_packages = Path(__file__).resolve().parents[1] / ".tools" / "noise-python"
    if local_packages.is_dir() and str(local_packages) not in sys.path:
        sys.path.insert(0, str(local_packages))
    sys.path.insert(0, str(directory))
    for path in sorted(directory.glob("*.py")):
        if path.name.startswith("_"):
            continue
        try:
            module = types.ModuleType(path.stem)
            module.__file__ = str(path)
            # Compile actual source every time, including same-second saves.
            exec(compile(path.read_text(encoding="utf-8-sig"), str(path), "exec"), module.__dict__)
            if not callable(getattr(module, "generate", None)):
                raise ValueError("Missing generate(count, seed, **params) function")
            primitive = getattr(module, "PRIMITIVE", "points")
            if primitive not in ("points", "lines"):
                raise ValueError("PRIMITIVE must be 'points' or 'lines'")
            population = primitive == "lines" and callable(getattr(module, "generate_population_source", None))
            parameters, keys = [], set()
            for entry in getattr(module, "PARAMETERS", []):
                key, kind = entry["key"], entry["type"]
                if not isinstance(key, str) or not key.isidentifier() or key in keys or key in ("count", "seed"):
                    raise ValueError(f"Invalid or duplicate parameter key: {key}")
                if key.startswith(("pp_", "pop_")):
                    raise ValueError("Parameter prefixes pp_ and pop_ are reserved for shared processing")
                if kind not in ("int", "float"):
                    raise ValueError(f"Unsupported parameter type: {kind}")
                lo, hi, default = entry["min"], entry["max"], entry["default"]
                if not all(isinstance(v, (int, float)) and not isinstance(v, bool) and math.isfinite(v)
                           for v in (lo, hi, default)) or not lo <= default <= hi:
                    raise ValueError(f"Invalid range/default for {key}")
                if kind == "int" and (any(int(v) != v for v in (lo, hi, default))
                                      or lo < -2147483648 or hi > 2147483647):
                    raise ValueError(f"Integer parameter out of range: {key}")
                if max(abs(lo), abs(hi)) > 1e20:
                    raise ValueError(f"Parameter range too large: {key}")
                keys.add(key)
                parameters.append(dict(key=key, label=str(entry.get("label", key)), type=kind,
                                       min=lo, max=hi, default=default))
                for hint in ('group', 'enabled_if', 'toggle', 'logarithmic', 'slider_max'):
                    if hint in entry:
                        parameters[-1][hint] = entry[hint]
            axis_fade = getattr(module, 'NATIVE_AXIS_FADE', False)
            if "fade" not in keys and not axis_fade:
                parameters.append(dict(FADE_PARAMETER))
            else:
                for entry in parameters:
                    if entry["key"] == "fade":
                        entry.update(group="Edge fade", toggle=True)
            for shared in (FADE_WIDTH_PARAMETER, FADE_DENSITY_PARAMETER):
                if axis_fade:
                    continue
                if shared["key"] not in keys:
                    parameters.append(dict(shared))
                else:
                    for entry in parameters:
                        if entry["key"] == shared["key"]:
                            entry.update(group="Edge fade", enabled_if="fade")
            parameters.extend(dict(entry) for entry in APPEARANCE_PARAMETERS)
            if primitive == "points" and callable(getattr(module, "generate_density_source", None)):
                # Field guidance has no random curve length or guide palette.
                parameters = [p for p in parameters if p['key'] not in ('pp_curve_length', 'pp_curve_colors')]
                for entry in parameters:
                    if entry.get('group') == 'Sparse curves':
                        entry['group'] = 'Density alignment'
                    if entry['key'] == 'pp_curves':
                        entry['label'] = 'Align sparse stars to density'
                    if entry['key'] == 'pp_curve_reach':
                        entry['label'] = 'Maximum alignment travel (units)'
                parameters.append(dict(key='pp_density_radius', label='Field smoothing (units)',
                    type='float', default=.25, min=.02, max=3., group='Density alignment', enabled_if='pp_curves'))
            # Independent line endpoint pairs cannot be thinned, merged or moved
            # by star postprocessors without breaking the skeleton topology.
            if primitive == "lines" and not population:
                parameters = [p for p in parameters if p["key"] in keys]
            if population:
                parameters.extend(dict(entry) for entry in POPULATION_PARAMETERS)
                parameters.extend(dict(entry) for entry in LIGHTING_PARAMETERS)
                if callable(getattr(module, 'generate_population_density_source', None)):
                    parameters.append(dict(FIELD_PARAMETER))
            field_consumer = density_graph and path.stem in NATIVE_CURVE_GENERATORS | {'noise_filaments_branches'}
            if block_units and (path.stem in NATIVE_CURVE_GENERATORS or field_consumer):
                module._legacy_parameters = parameters
                parameters = block_schema(parameters)
            if field_consumer:
                parameters = [p for p in parameters if p['key'] not in FIELD_KEYS | {'frequency', 'curve_resolution'}]
                parameters = [dict(p) for p in FIELD_PARAMETERS] + parameters
                if path.stem in NATIVE_CURVE_GENERATORS:
                    signed_seeds = [dict(p) for p in module.GRID_PARAMETERS if p['key'] in ('seed_y_pos', 'seed_y_neg')]
                    parameters = [replacement for p in parameters if p['key'] != 'seed_spacing'
                                  for replacement in (signed_seeds if p['key'] == 'seed_y' else [p])]
                    parameters.extend(dict(p) for p in module.GRID_PARAMETERS if p['key'] not in ('seed_y_pos', 'seed_y_neg'))
                    for entry in parameters:
                        if entry['key'] == 'strand_length':
                            entry['label'] = 'Mean curve length (blocks)'
            from _zone_controls import annotate_zones
            parameters = annotate_zones(parameters)
            if len(parameters) > 96:
                raise ValueError("Maximum 96 parameters per generator")
            catalog.append(dict(id=path.stem, name=str(getattr(module, "NAME", path.stem)),
                                primitive=primitive, population=population, parameters=parameters))
            modules[path.stem] = module
        except Exception:
            errors.append(f"{path.name}:\n{traceback.format_exc(limit=5)}")
    return catalog, modules, errors


def generate_request(request, directory, output):
    import numpy as np

    block_units = request.get('world_units') == 'blocks'
    density_graph = block_units and request.get('density_graph', False)
    catalog, modules, errors = load_catalog(directory, block_units=block_units, density_graph=density_graph)
    response = dict(catalog=catalog, warnings=errors)
    selected = request.get("generator", "")
    if not selected and catalog:
        selected = next((item["id"] for item in catalog if item["id"] == "galaxy"), catalog[0]["id"])
    if selected not in modules:
        response.update(ok=False, error="Generator unavailable: " + selected + "\n" + "\n".join(errors))
        return response
    try:
        count, seed = request.get("count", 100000), request.get("seed", 42)
        if type(count) is not int or not 1 <= count <= MAX_POINTS:
            raise ValueError(f"count must be an integer in [1, {MAX_POINTS}]")
        if type(seed) is not int or not 0 <= seed <= 2147483647:
            raise ValueError("seed must be an integer in [0, 2147483647]")
        schema = next(item for item in catalog if item["id"] == selected)
        supplied = request.get("params", {})
        if not isinstance(supplied, dict):
            raise ValueError("params must be an object")
        field_consumer = density_graph and selected in NATIVE_CURVE_GENERATORS | {'noise_filaments_branches'}
        native_blocks = block_units and (selected in NATIVE_CURVE_GENERATORS or field_consumer)
        if native_blocks and not supplied and schema['population']:
            supplied = {'pop_block_scale': 16}
        migrate = getattr(modules[selected], 'migrate_parameters', None)
        if callable(migrate):
            supplied = migrate(supplied)
        if schema['population']:
            supplied = migrate_population(supplied)
            supplied = migrate_lighting(supplied)
        if native_blocks:
            supplied = migrate_to_blocks(supplied, modules[selected]._legacy_parameters,
                direct_scale=float(request.get('legacy_display_scale', 16)) if not schema['population'] else None)
        if field_consumer:
            upstream = request.get('density_field', {})
            if not isinstance(upstream, dict):
                raise ValueError('density_field must be an object')
            supplied.update({p['key']: p['default'] for p in FIELD_PARAMETERS})
            supplied.update({key: value for key, value in upstream.items() if key in FIELD_KEYS})
        if request.get('shared_density_field') and selected in ('density_filament_curves', 'noise_filaments_branches'):
            # Equivalent physical settings can exceed the other consumer's old
            # slider range. Include inherited distances instead of silently
            # clipping the shared field when switching generators.
            for entry in schema['parameters']:
                if entry['key'] not in ('extent', 'y_extent', 'noise_scale', 'frequency'):
                    continue
                value = supplied.get(entry['key'])
                if isinstance(value, (int, float)) and not isinstance(value, bool) and math.isfinite(value) and 0 < value <= 1e6:
                    entry['min'] = min(entry['min'], value)
                    entry['max'] = max(entry['max'], value)
        params = {}
        for entry in schema["parameters"]:
            value = supplied.get(entry["key"], entry["default"])
            if not isinstance(value, (int, float)) or isinstance(value, bool) or not math.isfinite(value):
                raise ValueError(f"Invalid value for {entry['key']}")
            value = max(entry["min"], min(entry["max"], value))
            params[entry["key"]] = int(value) if entry["type"] == "int" else float(value)
        if native_blocks:
            params['_block_units'] = 1
        returned_params = {k: v for k, v in params.items() if not field_consumer or k not in FIELD_KEYS}
        if field_consumer:
            response['density_field'] = {k: params[k] for k in FIELD_KEYS}
        # Normalize settings even if subsequent geometry generation fails. The
        # UI must never draw native sliders over an unconverted saved preset.
        response.update(generator=selected, params=returned_params)
        started = time.perf_counter()
        module = modules[selected]
        primitive = schema["primitive"]
        block_scale = params.get('pop_blocks', params.get('pop_block_scale', 0)) if schema['population'] else 0
        # Only comparison experiments retain an output adapter. Native curves,
        # population and postprocessing already share block coordinates.
        display_scale = float(request.get('legacy_display_scale', 16)) if block_units and not native_blocks else 1.
        if not math.isfinite(display_scale) or not 1 <= display_scale <= 128:
            raise ValueError('Invalid legacy display scale')
        if block_scale and (params.get('pp_merge', 0) or params.get('pp_curves', 0)):
            raise ValueError('Block sampling requires Merge dense stars and Align sparse stars off; these edit continuous stars')
        requested_count = count
        native_keys = {entry["key"] for entry in getattr(module, "PARAMETERS", [])}
        if field_consumer:
            native_keys |= FIELD_KEYS
            native_keys |= {p['key'] for p in getattr(module, 'GRID_PARAMETERS', [])}
        # Existing density generators own their fade stage; all others receive
        # the shared point-stage fallback without changing their signatures.
        native_params = {key: value for key, value in params.items() if key in native_keys}
        density_source = None
        population_density = None
        if schema["population"]:
            if params.get('pop_source_density', 0) > 0:
                generated, paths, path_colors, population_density = module.generate_population_density_source(count=count, seed=seed, **native_params)
            else:
                generated, paths, path_colors = module.generate_population_source(count=count, seed=seed, **native_params)
        elif primitive == "points" and params.get('pp_curves', 0) and callable(getattr(module, 'generate_density_source', None)):
            generated, density, half_extents = module.generate_density_source(count=count, seed=seed, **native_params)
            density_source = (density, half_extents)
        else:
            generated = module.generate(count=count, seed=seed, **native_params)
        if not isinstance(generated, (tuple, list)) or len(generated) not in (2, 3):
            raise ValueError("generate must return (positions, colors) or (positions, colors, sizes)")
        positions, colors = generated[:2]
        positions = np.asarray(positions, dtype=np.float32)
        if primitive == "lines":
            if positions.ndim != 2 or positions.shape[1] != 3:
                raise ValueError("Line positions must have shape (N, 3)")
            count = len(positions)
            if not 2 <= count <= MAX_POINTS or count % 2:
                raise ValueError("Lines require an even vertex count in [2, 1000000]")
        sizes = np.asarray(generated[2] if len(generated) == 3 else 0.04, dtype=np.float32)
        if sizes.ndim == 0:
            sizes = np.full(count, sizes, dtype=np.float32)
        if sizes.shape != (count,) or not np.isfinite(sizes).all() or ((sizes <= 0) | (sizes > 1000)).any():
            raise ValueError(f"sizes must be a scalar or ({count},) array of finite world sizes in (0, 1000]")
        positions = np.asarray(positions, dtype=np.float32)
        colors = np.asarray(colors, dtype=np.float32)
        if positions.shape != (count, 3) or colors.shape != (count, 3):
            raise ValueError(f"Expected two ({count}, 3) arrays; got {positions.shape} and {colors.shape}")
        if not np.isfinite(positions).all() or not np.isfinite(colors).all():
            raise ValueError("Positions and colors must be finite")
        if (np.abs(positions) > 1e6).any():
            raise ValueError("Position magnitude exceeds 1,000,000 units")
        if ((colors < 0) | (colors > 1)).any():
            raise ValueError("RGB colors must be in [0, 1]")
        if primitive == "points" and (params.get("fade", 0) or any(params.get(key, 0) for key in ("pp_curves", "pp_merge", "pp_warp"))):
            bounds_function = getattr(module, "postprocess_bounds", None)
            bounds = bounds_function(**native_params) if callable(bounds_function) else None
            post_params = dict(params)
            if "fade" in native_keys:
                post_params["fade"] = 0
            positions, colors, sizes = apply_to_stars(positions, colors, sizes, seed, post_params, bounds,
                                                     density_source=density_source)
            if (not np.isfinite(positions).all() or not np.isfinite(colors).all()
                    or not np.isfinite(sizes).all() or (np.abs(positions) > 1e6).any()
                    or ((colors < 0) | (colors > 1)).any() or ((sizes <= 0) | (sizes > 1000)).any()):
                raise ValueError("Postprocessing produced invalid star attributes")
        block_bounds = None
        if block_scale:
            from _block_population import warp_positions
            bounds_function = getattr(module, 'postprocess_bounds', None)
            if callable(bounds_function):
                center, half = bounds_function(**native_params)
            else:
                low, high = positions.min(axis=0), positions.max(axis=0)
                center, half = (low+high)*.5, (high-low)*.5
            block_bounds = ((np.asarray(center), np.asarray(half)) if native_blocks else
                            (np.asarray(center)*block_scale, np.asarray(half)*block_scale))
            positions = warp_positions(positions.astype(float), paths, seed, params)
            if (not np.isfinite(positions).all() or (np.abs(positions) > 1e6).any()
                    or not np.isfinite(sizes).all() or (sizes > 1000).any()):
                raise ValueError('Warped curve preview exceeds coordinate/size limits')
        count = len(positions)
        points = np.empty((count, 7), dtype="<f4")
        points[:, :3], points[:, 3:6], points[:, 6] = positions, colors, sizes
        if display_scale != 1:
            points[:, :3] *= display_scale
            points[:, 6] *= display_scale
        with output.open("wb") as stream:
            stream.write(struct.pack("<8sQ", b"FSTAR002", count))
            stream.write(points.tobytes())
        if schema["population"]:
            stars, stats = populate_curves(paths, path_colors, seed, params, limit=MAX_POINTS,
                                          density_source=population_density)
            star_shapes = stats.pop('_block_shapes', None)
            star_kinds = stats.pop('_block_kinds', None)
            fade_groups = stats.pop('_fade_groups', None)
            source_positions = stars[0]
            bounds_function = getattr(module, 'postprocess_bounds', None)
            bounds = bounds_function(**native_params) if callable(bounds_function) else None
            post_params = params
            if block_scale:
                # Geometry was warped before cell integration.
                # Only survival/appearance operations may follow block selection.
                bounds = block_bounds
                post_params = dict(params, pp_warp=0)
                if stats['block_integration_limited']:
                    errors.append('Block integration probe budget reached; fine cell probabilities are approximate. Reduce scale, spread, or curve density.')
            stars = apply_to_stars(*stars, seed, post_params, bounds=bounds, allow_empty=True,
                                   axis_fade=getattr(module, 'POPULATION_AXIS_FADE', False),
                                   fade_groups=fade_groups)
            star_positions, star_colors, star_sizes = (np.asarray(a, dtype=np.float32) for a in stars)
            if star_shapes is not None:
                # Block postprocessing only removes cells. Preserve each survivor's
                # shape by matching its sorted XYZ cell center before display scaling.
                xyz = np.dtype([('x', '<f4'), ('y', '<f4'), ('z', '<f4')])
                original = np.ascontiguousarray(source_positions, dtype='<f4').view(xyz).reshape(-1)
                surviving = np.ascontiguousarray(star_positions, dtype='<f4').view(xyz).reshape(-1)
                survivors = np.searchsorted(original, surviving)
                star_shapes = star_shapes[survivors]
                star_kinds = star_kinds[survivors]
                # Still in actual block coordinates, after all source-removing fades.
                star_colors = apply_lighting(star_positions, star_colors, star_kinds, params)
            if block_scale and not native_blocks:
                star_positions = star_positions / block_scale
                star_sizes = star_sizes / block_scale
            if display_scale != 1:
                star_positions = star_positions * display_scale
                star_sizes = star_sizes * display_scale
            star_count = len(star_positions)
            if (star_count > MAX_POINTS or star_positions.shape != (star_count, 3)
                    or star_colors.shape != (star_count, 3) or star_sizes.shape != (star_count,)
                    or not all(np.isfinite(a).all() for a in (star_positions, star_colors, star_sizes))
                    or (np.abs(star_positions) > 1e6).any() or ((star_colors < 0) | (star_colors > 1)).any()
                    or ((star_sizes <= 0) | (star_sizes > 1000)).any()):
                raise ValueError("Invalid populated star attributes")
            packed = np.column_stack((star_positions, star_colors, star_sizes)).astype("<f4")
            magic = b"FSTAR002"
            if star_shapes is not None:
                if (star_shapes.shape != (star_count, 3) or not np.isfinite(star_shapes).all()
                        or ((star_shapes <= 0) | (star_shapes > 1)).any()):
                    raise ValueError("Invalid block proxy dimensions")
                packed = np.column_stack((packed, star_shapes)).astype('<f4')
                magic = b"FSTAR003"
            with output.with_suffix(".stars.bin").open("wb") as stream:
                stream.write(struct.pack("<8sQ", magic, star_count))
                stream.write(packed.tobytes())
            response.update(star_count=star_count, **stats)
        response.update(ok=True, generator=selected, params=returned_params, primitive=primitive,
                        population=schema["population"],
                        count=count, requested_count=requested_count,
                        generation_ms=(time.perf_counter() - started) * 1000)
    except Exception:
        response.update(ok=False, error=traceback.format_exc(limit=8))
    return response


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--request", type=Path)
    parser.add_argument("--response", type=Path)
    parser.add_argument("--points", type=Path)
    parser.add_argument("--serve", action='store_true')
    parser.add_argument("--generators", type=Path, required=True)
    args = parser.parse_args()
    if args.serve:
        # Native service serializes requests and restarts us on source changes,
        # cancellation or timeout. Idle workers block on stdin without polling.
        for line in sys.stdin:
            command = json.loads(line)
            response_path = Path(command['response'])
            try:
                request = json.loads(Path(command['request']).read_text(encoding='utf-8'))
                response = generate_request(request, args.generators.resolve(), Path(command['points']))
            except Exception:
                response = dict(ok=False, error=traceback.format_exc(limit=8), catalog=[], warnings=[])
            response['worker_pid'] = __import__('os').getpid()
            temporary = response_path.with_suffix('.tmp')
            temporary.write_text(json.dumps(response, allow_nan=False), encoding='utf-8')
            temporary.replace(response_path)
        return
    if args.request is None or args.response is None or args.points is None:
        parser.error('--request, --response and --points are required without --serve')
    try:
        request = json.loads(args.request.read_text(encoding="utf-8"))
        response = generate_request(request, args.generators.resolve(), args.points)
    except Exception:
        response = dict(ok=False, error=traceback.format_exc(limit=8), catalog=[], warnings=[])
    args.response.write_text(json.dumps(response, allow_nan=False), encoding="utf-8")


if __name__ == "__main__":
    main()
