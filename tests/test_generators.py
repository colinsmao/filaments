"""CPU-only tests and an optional local benchmark; never opens the viewer."""
import importlib.util
from pathlib import Path
import tempfile
import time
import unittest

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("worker", ROOT / "python" / "worker.py")
worker = importlib.util.module_from_spec(spec)
spec.loader.exec_module(worker)


class Generators(unittest.TestCase):
    def test_seed_shapes_ranges_and_parameter_effect(self):
        catalog, modules, errors = worker.load_catalog(ROOT / "generators")
        self.assertFalse(errors)
        for entry in catalog:
            module = modules[entry["id"]]
            for count in (1, 10000):
                a, color, sizes = module.generate(count, 42)
                b, _, repeated_sizes = module.generate(count, 42)
                self.assertEqual(a.shape, (count, 3))
                self.assertEqual(color.shape, (count, 3))
                np.testing.assert_array_equal(a, b)
                np.testing.assert_array_equal(sizes, repeated_sizes)
                self.assertEqual(sizes.shape, (count,))
                self.assertTrue(np.isfinite(sizes).all() and (sizes > 0).all())
                self.assertTrue(np.isfinite(a).all())
                self.assertTrue(((color >= 0) & (color <= 1)).all())
            other, _, _ = module.generate(10000, 43)
            self.assertFalse(np.array_equal(a, other))
            changed, _, _ = module.generate(10000, 42, **{entry["parameters"][0]["key"]: 15.0})
            self.assertGreater(np.linalg.norm(changed, axis=1).mean(), np.linalg.norm(a, axis=1).mean())
            same, same_color, uniform = module.generate(10000, 42, star_size=0.1, size_variation=0)
            np.testing.assert_array_equal(same, a)
            np.testing.assert_array_equal(same_color, color)
            np.testing.assert_allclose(uniform, 0.1)
            self.assertGreater(np.ptp(sizes), 0)

    def test_request_validation_and_binary_layout(self):
        with tempfile.TemporaryDirectory() as temp:
            output = Path(temp) / "stars.bin"
            for count in (0, -1, 1000001, 1.5):
                result = worker.generate_request(dict(generator="galaxy", count=count), ROOT / "generators", output)
                self.assertFalse(result["ok"])
            result = worker.generate_request(dict(generator="galaxy", count=100, params={"radius": 999}), ROOT / "generators", output)
            self.assertTrue(result["ok"])
            self.assertEqual(result["params"]["radius"], 30)
            self.assertEqual(output.stat().st_size, 16 + 100 * 28)
            self.assertEqual(output.read_bytes()[:8], b"FSTAR002")

    def test_per_star_sizes_and_legacy_scripts(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            output = root / "stars.bin"
            script = root / "test.py"
            prefix = "import numpy as np\ndef generate(count, seed):\n    return np.zeros((count,3)), np.ones((count,3))"
            for suffix, expected in (("", [0.04] * 3), (", 0.2", [0.2] * 3),
                                     (", np.array([0.1, 0.2, 0.3])", [0.1, 0.2, 0.3])):
                script.write_text(prefix + suffix)
                result = worker.generate_request(dict(generator="test", count=3), root, output)
                self.assertTrue(result["ok"], result)
                data = np.frombuffer(output.read_bytes()[16:], dtype="<f4").reshape(3, 7)
                np.testing.assert_allclose(data[:, 6], expected)
            for suffix in (", 0", ", -1", ", np.nan", ", np.inf", ", 1001", ", np.ones((3,1))", ", np.ones(2)"):
                script.write_text(prefix + suffix)
                result = worker.generate_request(dict(generator="test", count=3), root, output)
                self.assertFalse(result["ok"], suffix)


if __name__ == "__main__":
    import sys
    if "--benchmark" in sys.argv:
        with tempfile.TemporaryDirectory() as temp:
            for mode in ("galaxy", "filaments"):
                for count in (100000, 1000000):
                    start = time.perf_counter()
                    result = worker.generate_request(dict(generator=mode, count=count, seed=42), ROOT / "generators", Path(temp) / "points.bin")
                    assert result["ok"], result
                    print(f"{mode}: {count:,} points; math/validation/packing {result['generation_ms']:.1f} ms; in-process total {(time.perf_counter()-start)*1000:.1f} ms")
    else:
        unittest.main()
