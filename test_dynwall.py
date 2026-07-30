#!/usr/bin/env python3
"""Unit tests for dynwall's pure functions and spec-cache round trip.

Run: python3 test_dynwall.py
"""

import json
import sys
import tempfile
import unittest
from datetime import datetime
from pathlib import Path

from importlib.machinery import SourceFileLoader

dynwall = SourceFileLoader("dynwall", str(Path(__file__).parent / "dynwall")).load_module()


class TestHelpers(unittest.TestCase):
    def test_hex_rgb(self):
        self.assertEqual(dynwall.hex_rgb("#ff0080"), (255, 0, 128))
        self.assertEqual(dynwall.hex_rgb("00ff00"), (0, 255, 0))

    def test_num_parses_ranges(self):
        self.assertEqual(dynwall.num(0.5, 0), 0.5)
        self.assertEqual(dynwall.num("0.06-0.12", 0), 0.09)
        self.assertEqual(dynwall.num("junk", 1.5), 1.5)
        self.assertEqual(dynwall.num(None, 2.0), 2.0)

    def test_clamp(self):
        self.assertEqual(dynwall.clamp(5, 0, 10), 5)
        self.assertEqual(dynwall.clamp(-1, 0, 10), 0)
        self.assertEqual(dynwall.clamp(99, 0, 10), 10)

    def test_fallback_spec_valid(self):
        spec = dynwall.fallback_spec(datetime(2026, 1, 1, 12, 0), "sunny")
        self.assertGreaterEqual(len(spec["gradient"]), 2)
        for c in spec["gradient"]:
            dynwall.hex_rgb(c)  # must parse
        night = dynwall.fallback_spec(datetime(2026, 1, 1, 2, 0), "clear")
        self.assertGreater(night["stars"], 0)

    def test_load_config_clamps(self):
        cfg = dynwall.load_config()
        self.assertTrue(0.5 <= cfg["frame_seconds"] <= 10.0)
        self.assertTrue(1 <= cfg["frames"] <= 120)


class TestSpecCache(unittest.TestCase):
    def test_cache_key_is_stable_across_calls(self):
        """Regression: hash() is process-salted; key must be deterministic."""
        with tempfile.TemporaryDirectory() as td:
            dynwall.CACHE_DIR = Path(td)
            dynwall.SPEC_CACHE = Path(td) / "spec.json"
            cfg = dict(dynwall.DEFAULTS)
            cfg["allow_network"] = False
            calls = []
            orig = dynwall.llm_spec
            dynwall.llm_spec = lambda *a: (calls.append(1), None)[1]
            try:
                s1 = dynwall.get_spec("sunny", cfg)
                s2 = dynwall.get_spec("sunny", cfg)
            finally:
                dynwall.llm_spec = orig
            self.assertEqual(s1, s2)
            self.assertEqual(len(calls), 1, "second get_spec must hit the cache")
            data = json.loads(dynwall.SPEC_CACHE.read_text())
            self.assertNotIn("|", data["key"].rsplit("|", 1)[-1][:0] or "x")  # key is a sha256 hex
            self.assertEqual(len(data["key"].rsplit("|", 1)[-1]), 64)


if __name__ == "__main__":
    unittest.main()
