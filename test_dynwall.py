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
from unittest.mock import patch
from PIL import ImageChops, ImageStat

from importlib.machinery import SourceFileLoader

dynwall = SourceFileLoader("dynwall", str(Path(__file__).parent / "dynwall")).load_module()


class TestHelpers(unittest.TestCase):
    def test_hex_rgb(self):
        self.assertEqual(dynwall.hex_rgb("#ff0080"), (255, 0, 128))
        self.assertEqual(dynwall.hex_rgb("00ff00"), (0, 255, 0))

    def test_hex_rgb_tolerates_bad_llm_colors(self):
        fb = (136, 136, 136)
        self.assertEqual(dynwall.hex_rgb("red"), fb)
        self.assertEqual(dynwall.hex_rgb("#ff00"), fb)
        self.assertEqual(dynwall.hex_rgb(None), fb)
        self.assertEqual(dynwall.hex_rgb("#zzzzzz"), fb)

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
    def test_default_prompt_edits_invalidate_the_art_cache(self):
        with tempfile.TemporaryDirectory() as td, \
             patch.object(dynwall, "CACHE_DIR", Path(td)), \
             patch.object(dynwall, "SPEC_CACHE", Path(td) / "spec.json"), \
             patch.object(dynwall, "llm_spec", return_value=None) as llm:
            cfg = dict(dynwall.DEFAULTS, allow_network=False)
            with patch.object(dynwall, "get_default_prompt", return_value="Paint a copper sky"):
                dynwall.get_spec("clear", cfg)
                dynwall.get_spec("clear", cfg)
            with patch.object(dynwall, "get_default_prompt", return_value="Paint a teal sky"):
                dynwall.get_spec("clear", cfg)
            self.assertEqual(llm.call_count, 2)

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
            prompt_hash = data["key"].rsplit("|", 1)[-1]
            self.assertEqual(len(prompt_hash), 64)
            int(prompt_hash, 16)  # must be a sha256 hex digest


class TestArtDirection(unittest.TestCase):
    def test_vignette_keeps_the_center_bright_and_gently_darkens_edges(self):
        spec = {"gradient": ["#a0a0a0", "#a0a0a0"], "mesh": {"style": "none"},
                "landscape": {"style": "none"}, "grain": 0, "vignette": .3}
        with patch.object(dynwall, "W", 160), patch.object(dynwall, "H", 80):
            image = dynwall.compose(dynwall.build_scene(spec), 0, 0)
        self.assertGreater(image.getpixel((80, 40))[0], 155)
        self.assertTrue(130 < image.getpixel((0, 0))[0] < image.getpixel((80, 40))[0])

    def test_custom_prompt_keeps_the_renderers_contract_and_actual_canvas(self):
        cfg = dict(dynwall.DEFAULTS, prompt="Give the evening a copper glow.", width=2560, height=1440)
        prompt = dynwall.build_art_prompt(datetime(2026, 10, 30, 18, 15), "Observed light rain", cfg)
        self.assertIn(cfg["prompt"], prompt)
        self.assertIn("2026-10-30", prompt)
        self.assertIn("18:15", prompt)
        self.assertIn("2560x1440", prompt)
        self.assertIn("Observed light rain", prompt)
        for field in ('"gradient"', '"landscape"', '"celestial"', '"gradient_positions"'):
            self.assertIn(field, prompt)

    def test_shipped_prompt_matches_the_embedded_fallback(self):
        shipped = (Path(__file__).parent / "default_prompt.txt").read_text().strip()
        self.assertEqual(dynwall.EMBEDDED_DEFAULT_PROMPT.strip(), shipped)

    def test_offline_scenes_have_rich_distinct_day_phase_palettes(self):
        palettes = set()
        for hour in (2, 7, 12, 18):
            spec = dynwall.fallback_spec(datetime(2026, 10, 30, hour), "clear")
            self.assertEqual(len(spec["gradient"]), 5)
            self.assertIsInstance(spec["glow"], dict)
            self.assertEqual(spec["landscape"]["style"], "hills")
            self.assertLessEqual(spec["vignette"], .35)
            json.dumps(spec, allow_nan=False)
            palettes.add(tuple(spec["gradient"]))
        self.assertEqual(len(palettes), 4)

    def test_offline_palette_evolves_smoothly_and_takes_seasonal_inspiration(self):
        autumn = dynwall.fallback_spec(datetime(2026, 10, 30, 12), "clear")
        summer = dynwall.fallback_spec(datetime(2026, 7, 30, 12), "clear")
        self.assertNotEqual(autumn["gradient"], summer["gradient"])
        before = dynwall.fallback_spec(datetime(2026, 10, 30, 17, 59), "clear")
        after = dynwall.fallback_spec(datetime(2026, 10, 30, 18), "clear")
        for a, b in zip(before["gradient"], after["gradient"]):
            self.assertLess(max(abs(x-y) for x,y in zip(dynwall.hex_rgb(a), dynwall.hex_rgb(b))), 5)

    def test_landscape_adds_depth_below_the_skyline_in_the_static_fallback(self):
        spec = {"gradient": ["#728ba2", "#b5c1c8"], "mesh": {"style": "none"},
                "grain": 0, "vignette": 0, "landscape": {"style": "hills", "height": .2, "mist": .5}}
        with patch.object(dynwall, "W", 320), patch.object(dynwall, "H", 120):
            sky = dynwall.compose(dynwall.build_scene(spec, landscape_enabled=False), 0, 0)
            hills = dynwall.compose(dynwall.build_scene(spec), 0, 0)
        delta = ImageChops.difference(sky, hills)
        self.assertIsNone(delta.crop((0, 0, 320, 75)).getbbox())
        self.assertGreater(sum(ImageStat.Stat(delta.crop((0, 95, 320, 120))).mean), 10)

    def test_single_pixel_canvas_renders(self):
        with patch.object(dynwall, "W", 1), patch.object(dynwall, "H", 1):
            image = dynwall.compose(dynwall.build_scene({"gradient": ["#123456", "#789abc"]}), 0, 0)
        self.assertEqual(image.size, (1, 1))


if __name__ == "__main__":
    unittest.main()
