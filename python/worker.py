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
from _population import PARAMETERS as POPULATION_PARAMETERS, populate_curves


def load_catalog(directory):
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
            if "fade" not in keys:
                parameters.append(dict(FADE_PARAMETER))
            else:
                for entry in parameters:
                    if entry["key"] == "fade":
                        entry.update(group="Edge fade", toggle=True)
            for shared in (FADE_WIDTH_PARAMETER, FADE_DENSITY_PARAMETER):
                if shared["key"] not in keys:
                    parameters.append(dict(shared))
                else:
                    for entry in parameters:
                        if entry["key"] == shared["key"]:
                            entry.update(group="Edge fade", enabled_if="fade")
            parameters.extend(dict(entry) for entry in APPEARANCE_PARAMETERS)
            # Independent line endpoint pairs cannot be thinned, merged or moved
            # by star postprocessors without breaking the skeleton topology.
            if primitive == "lines" and not population:
                parameters = [p for p in parameters if p["key"] in keys]
            if population:
                parameters.extend(dict(entry) for entry in POPULATION_PARAMETERS)
            if len(parameters) > 64:
                raise ValueError("Maximum 64 parameters per generator")
            catalog.append(dict(id=path.stem, name=str(getattr(module, "NAME", path.stem)),
                                primitive=primitive, population=population, parameters=parameters))
            modules[path.stem] = module
        except Exception:
            errors.append(f"{path.name}:\n{traceback.format_exc(limit=5)}")
    return catalog, modules, errors


def generate_request(request, directory, output):
    import numpy as np

    catalog, modules, errors = load_catalog(directory)
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
        params = {}
        for entry in schema["parameters"]:
            value = supplied.get(entry["key"], entry["default"])
            if not isinstance(value, (int, float)) or isinstance(value, bool) or not math.isfinite(value):
                raise ValueError(f"Invalid value for {entry['key']}")
            value = max(entry["min"], min(entry["max"], value))
            params[entry["key"]] = int(value) if entry["type"] == "int" else float(value)
        started = time.perf_counter()
        module = modules[selected]
        primitive = schema["primitive"]
        requested_count = count
        native_keys = {entry["key"] for entry in getattr(module, "PARAMETERS", [])}
        # Existing density generators own their fade stage; all others receive
        # the shared point-stage fallback without changing their signatures.
        native_params = {key: value for key, value in params.items() if key in native_keys}
        if schema["population"]:
            generated, paths, path_colors = module.generate_population_source(count=count, seed=seed, **native_params)
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
            positions, colors, sizes = apply_to_stars(positions, colors, sizes, seed, post_params, bounds)
            if (not np.isfinite(positions).all() or not np.isfinite(colors).all()
                    or not np.isfinite(sizes).all() or (np.abs(positions) > 1e6).any()
                    or ((colors < 0) | (colors > 1)).any() or ((sizes <= 0) | (sizes > 1000)).any()):
                raise ValueError("Postprocessing produced invalid star attributes")
        count = len(positions)
        points = np.empty((count, 7), dtype="<f4")
        points[:, :3], points[:, 3:6], points[:, 6] = positions, colors, sizes
        with output.open("wb") as stream:
            stream.write(struct.pack("<8sQ", b"FSTAR002", count))
            stream.write(points.tobytes())
        if schema["population"]:
            stars, stats = populate_curves(paths, path_colors, seed, params, limit=MAX_POINTS)
            stars = apply_to_stars(*stars, seed, params, allow_empty=True)
            star_positions, star_colors, star_sizes = (np.asarray(a, dtype=np.float32) for a in stars)
            star_count = len(star_positions)
            if (star_count > MAX_POINTS or star_positions.shape != (star_count, 3)
                    or star_colors.shape != (star_count, 3) or star_sizes.shape != (star_count,)
                    or not all(np.isfinite(a).all() for a in (star_positions, star_colors, star_sizes))
                    or (np.abs(star_positions) > 1e6).any() or ((star_colors < 0) | (star_colors > 1)).any()
                    or ((star_sizes <= 0) | (star_sizes > 1000)).any()):
                raise ValueError("Invalid populated star attributes")
            packed = np.column_stack((star_positions, star_colors, star_sizes)).astype("<f4")
            with output.with_suffix(".stars.bin").open("wb") as stream:
                stream.write(struct.pack("<8sQ", b"FSTAR002", star_count))
                stream.write(packed.tobytes())
            response.update(star_count=star_count, **stats)
        response.update(ok=True, generator=selected, params=params, primitive=primitive,
                        population=schema["population"],
                        count=count, requested_count=requested_count,
                        generation_ms=(time.perf_counter() - started) * 1000)
    except Exception:
        response.update(ok=False, error=traceback.format_exc(limit=8))
    return response


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--request", type=Path, required=True)
    parser.add_argument("--response", type=Path, required=True)
    parser.add_argument("--points", type=Path, required=True)
    parser.add_argument("--generators", type=Path, required=True)
    args = parser.parse_args()
    try:
        request = json.loads(args.request.read_text(encoding="utf-8"))
        response = generate_request(request, args.generators.resolve(), args.points)
    except Exception:
        response = dict(ok=False, error=traceback.format_exc(limit=8), catalog=[], warnings=[])
    args.response.write_text(json.dumps(response, allow_nan=False), encoding="utf-8")


if __name__ == "__main__":
    main()
