#!/usr/bin/env python3
"""Tests for Dynwall's weather snapshot and scene helpers."""

import json
import math
import os
import stat
import tempfile
import unittest
from copy import deepcopy
from pathlib import Path
from unittest.mock import patch

from dynwall_weather import (
    build_scene_document,
    load_weather,
    weather_description,
    write_scene,
)


def valid_snapshot(fetched_at=10_000_000):
    return {
        "schemaVersion": 1,
        "fetchedAt": fetched_at,
        "provider": "open-meteo",
        "location": "Detroit, Michigan",
        "unit": "c",
        "latitude": 42.3314,
        "longitude": -83.0458,
        "current": {
            "temp": 12.5,
            "desc": "Light rain",
            "isNight": False,
            "cloudCover": 73.25,
            "precipitation": 0.375,
            "rain": 0.125,
            "snowfall": None,
            "windSpeedKmh": 17.75,
            "windDirection": 359.5,
            "weatherCode": 61,
            "providerPeriodMinutes": 15,
        },
        "days": [{"date": "2026-09-12", "desc": "Rain"}],
    }


class LoadWeatherTests(unittest.TestCase):
    def write_snapshot(self, directory, snapshot):
        path = Path(directory) / "current.json"
        path.write_text(json.dumps(snapshot), encoding="utf-8")
        return path

    def test_loads_fresh_snapshot_and_retains_metadata_and_fractions(self):
        with tempfile.TemporaryDirectory() as td:
            snapshot = valid_snapshot()
            path = self.write_snapshot(td, snapshot)

            loaded = load_weather(path, now=10_000)

        self.assertEqual(loaded, snapshot)
        self.assertEqual(loaded["current"]["precipitation"], 0.375)
        self.assertEqual(loaded["current"]["windSpeedKmh"], 17.75)
        self.assertEqual(loaded["current"]["providerPeriodMinutes"], 15)
        self.assertEqual(loaded["days"], snapshot["days"])

    def test_uses_xdg_cache_path_or_home_cache_fallback(self):
        snapshot = valid_snapshot()
        with tempfile.TemporaryDirectory() as td:
            xdg = Path(td) / "xdg"
            path = xdg / "topweather" / "current.json"
            path.parent.mkdir(parents=True)
            path.write_text(json.dumps(snapshot), encoding="utf-8")
            with patch.dict(os.environ, {"XDG_CACHE_HOME": str(xdg)}, clear=False):
                self.assertEqual(load_weather(now=10_000), snapshot)

        with tempfile.TemporaryDirectory() as td:
            home = Path(td)
            path = home / ".cache" / "topweather" / "current.json"
            path.parent.mkdir(parents=True)
            path.write_text(json.dumps(snapshot), encoding="utf-8")
            with patch.dict(os.environ, {"HOME": str(home)}, clear=False):
                with patch.dict(os.environ, {}, clear=False):
                    os.environ.pop("XDG_CACHE_HOME", None)
                    self.assertEqual(load_weather(now=10_000), snapshot)

    def test_missing_metrics_are_normalized_to_null_not_zero(self):
        snapshot = valid_snapshot()
        snapshot["current"] = {"desc": "Conditions unavailable"}
        with tempfile.TemporaryDirectory() as td:
            loaded = load_weather(self.write_snapshot(td, snapshot), now=10_000)

        for field in (
            "cloudCover",
            "precipitation",
            "rain",
            "snowfall",
            "windSpeedKmh",
            "windDirection",
            "weatherCode",
        ):
            self.assertIsNone(loaded["current"][field])

    def test_rejects_snapshot_more_than_two_hours_old(self):
        with tempfile.TemporaryDirectory() as td:
            boundary = self.write_snapshot(td, valid_snapshot(fetched_at=2_800_000))
            self.assertIsNotNone(load_weather(boundary, now=10_000))
            stale = self.write_snapshot(td, valid_snapshot(fetched_at=2_799_999))
            self.assertIsNone(load_weather(stale, now=10_000))

    def test_rejects_snapshot_more_than_five_minutes_in_future(self):
        with tempfile.TemporaryDirectory() as td:
            boundary = self.write_snapshot(td, valid_snapshot(fetched_at=10_300_000))
            self.assertIsNotNone(load_weather(boundary, now=10_000))
            future = self.write_snapshot(td, valid_snapshot(fetched_at=10_300_001))
            self.assertIsNone(load_weather(future, now=10_000))

    def test_returns_none_for_missing_corrupt_or_wrong_shape_payload(self):
        with tempfile.TemporaryDirectory() as td:
            directory = Path(td)
            self.assertIsNone(load_weather(directory / "missing.json", now=10_000))
            corrupt = directory / "corrupt.json"
            corrupt.write_text("{not json", encoding="utf-8")
            self.assertIsNone(load_weather(corrupt, now=10_000))
            wrong_shape = directory / "wrong.json"
            wrong_shape.write_text("[]", encoding="utf-8")
            self.assertIsNone(load_weather(wrong_shape, now=10_000))

    def test_rejects_unknown_schema_unit_and_invalid_envelope_fields(self):
        mutations = {
            "unknown schema": ("schemaVersion", 2),
            "boolean schema": ("schemaVersion", True),
            "fractional schema": ("schemaVersion", 1.0),
            "unknown unit": ("unit", "kelvin"),
            "missing provider": ("provider", ""),
            "non-string location": ("location", 42),
            "boolean timestamp": ("fetchedAt", True),
            "fractional timestamp": ("fetchedAt", 10_000_000.5),
            "missing current": ("current", None),
        }
        with tempfile.TemporaryDirectory() as td:
            for label, (field, value) in mutations.items():
                with self.subTest(label=label):
                    snapshot = valid_snapshot()
                    snapshot[field] = value
                    path = self.write_snapshot(td, snapshot)
                    self.assertIsNone(load_weather(path, now=10_000))

    def test_rejects_invalid_coordinates_and_current_measurements(self):
        mutations = (
            ("latitude", math.nan),
            ("latitude", True),
            ("latitude", 90.01),
            ("longitude", -180.01),
            ("cloudCover", -0.01),
            ("cloudCover", 100.01),
            ("precipitation", -0.01),
            ("rain", math.inf),
            ("snowfall", True),
            ("windSpeedKmh", -0.01),
            ("windSpeedKmh", 10**1000),
            ("windDirection", 360.01),
            ("windDirection", False),
            ("weatherCode", False),
        )
        with tempfile.TemporaryDirectory() as td:
            for field, value in mutations:
                with self.subTest(field=field, value=value):
                    snapshot = valid_snapshot()
                    target = snapshot if field in ("latitude", "longitude") else snapshot["current"]
                    target[field] = value
                    path = self.write_snapshot(td, snapshot)
                    self.assertIsNone(load_weather(path, now=10_000))


class WeatherDescriptionTests(unittest.TestCase):
    def test_describes_only_observed_context_and_preserves_fractions(self):
        description = weather_description(valid_snapshot())

        self.assertIn("Light rain", description)
        self.assertIn("12.5°C", description)
        self.assertIn("73.25% cloud cover", description)
        self.assertIn("0.375 mm/h precipitation", description)
        self.assertIn("17.75 km/h wind", description)
        self.assertIn("359.5°", description)
        self.assertIn("Detroit, Michigan", description)

    def test_reports_unavailable_weather_without_fabricated_metrics(self):
        self.assertEqual(weather_description(None), "Weather data unavailable")
        snapshot = valid_snapshot()
        snapshot["current"] = {
            "desc": "Conditions unavailable",
            "cloudCover": None,
            "precipitation": None,
            "rain": None,
            "snowfall": None,
            "windSpeedKmh": None,
            "windDirection": None,
            "weatherCode": None,
        }
        description = weather_description(snapshot)
        self.assertNotIn("0 mm", description)
        self.assertNotIn("0%", description)
        self.assertIn("Conditions unavailable", description)


class SceneDocumentTests(unittest.TestCase):
    def test_landscape_switch_overrides_art_direction_without_mutating_it(self):
        spec = {"gradient": ["#123456", "#789abc"], "landscape": {"style": "hills", "height": .2}}
        document = build_scene_document(spec, None, {"landscape_enabled": False}, now=10_000)
        self.assertEqual(document["spec"]["landscape"]["style"], "none")
        self.assertEqual(spec["landscape"]["style"], "hills")

    def test_seasonal_effects_setting_reaches_the_renderer(self):
        for value, expected in ((True, True), (False, False), ("false", True), (None, True)):
            with self.subTest(value=value):
                document = build_scene_document({}, None, {"seasonal_effects": value}, now=10_000)
                self.assertIs(document["renderer"]["seasonalEffects"], expected)

    def test_builds_scene_schema_using_seconds_for_now_and_milliseconds_on_wire(self):
        spec = {"title": "September rain", "gradient": ["#123456", "#789abc"]}
        snapshot = valid_snapshot()

        document = build_scene_document(
            spec,
            snapshot,
            {"allow_animation": False, "weather_fps": 48, "weather_quality": "high"},
            now=10_000.125,
        )

        self.assertEqual(
            document,
            {
                "schemaVersion": 1,
                "generatedAt": 10_000_125,
                "spec": spec,
                "weather": snapshot,
                "renderer": {"enabled": False, "fps": 48, "quality": "high", "seasonalEffects": True},
                "living": {"background": "auto", "landscape_pack": "", "scene_customization": {
                    "horizon": .8, "terrain_scale": 1., "mist": .5, "warmth": 0., "darkness": 0., "animation_intensity": 1.},
                    "presets": {}, "favorites": [], "schedule": {"enabled": False, "entries": [], "rotation_minutes": 0},
                    "persistent_weather": True, "atmospheric_intensity": .5, "battery_saver": True, "landscape_enabled": True},
            },
        )
        self.assertIsNot(document["spec"], spec)
        self.assertIsNot(document["weather"], snapshot)

    def test_defaults_and_defensively_normalizes_renderer_config(self):
        spec = {"title": "Sky"}
        cases = (
            ({}, {"enabled": True, "fps": 30, "quality": "balanced"}),
            ({"weather_fps": 2}, {"enabled": True, "fps": 15, "quality": "balanced"}),
            ({"weather_fps": 100}, {"enabled": True, "fps": 60, "quality": "balanced"}),
            (
                {"allow_animation": "false", "weather_fps": True, "weather_quality": "unknown"},
                {"enabled": True, "fps": 30, "quality": "balanced"},
            ),
            ({"weather_quality": "HIGH"}, {"enabled": True, "fps": 30, "quality": "high"}),
        )
        for cfg, expected in cases:
            with self.subTest(cfg=cfg):
                document = build_scene_document(spec, None, cfg, now=10_000)
                self.assertEqual(document["renderer"], {**expected, "seasonalEffects": True})
                self.assertIsNone(document["weather"])

    def test_drops_stale_or_invalid_snapshot_from_scene(self):
        spec = {"title": "Sky"}
        stale = valid_snapshot(fetched_at=2_799_999)
        invalid = valid_snapshot()
        invalid["current"]["rain"] = -1

        self.assertIsNone(build_scene_document(spec, stale, {}, now=10_000)["weather"])
        self.assertIsNone(build_scene_document(spec, invalid, {}, now=10_000)["weather"])

    def test_disables_mesh_in_copied_spec_without_mutating_input(self):
        spec = {
            "title": "Faceted sky",
            "mesh": {"style": "lowpoly", "density": 18, "opacity": 0.1},
        }

        document = build_scene_document(
            spec, None, {"mesh_enabled": False}, now=10_000
        )

        self.assertEqual(
            document["spec"]["mesh"],
            {"style": "none", "density": 18, "opacity": 0.1},
        )
        self.assertEqual(
            spec["mesh"],
            {"style": "lowpoly", "density": 18, "opacity": 0.1},
        )


class WriteSceneTests(unittest.TestCase):
    def test_atomically_replaces_scene_with_private_permissions(self):
        document = build_scene_document({"title": "Sky"}, None, {}, now=10_000)
        with tempfile.TemporaryDirectory() as td:
            path = Path(td) / "nested" / "scene.json"
            path.parent.mkdir()
            path.write_text('{"old":true}', encoding="utf-8")
            path.chmod(0o644)
            old_inode = path.stat().st_ino

            write_scene(path, document)

            self.assertEqual(json.loads(path.read_text(encoding="utf-8")), document)
            self.assertEqual(stat.S_IMODE(path.stat().st_mode), 0o600)
            self.assertNotEqual(path.stat().st_ino, old_inode)
            self.assertEqual(list(path.parent.glob(f".{path.name}.*.tmp")), [])

    def test_failed_serialization_keeps_existing_scene_and_cleans_temp_file(self):
        with tempfile.TemporaryDirectory() as td:
            path = Path(td) / "scene.json"
            original = '{"old":true}\n'
            path.write_text(original, encoding="utf-8")

            with self.assertRaises(TypeError):
                write_scene(path, {"notJson": {1, 2, 3}})

            self.assertEqual(path.read_text(encoding="utf-8"), original)
            self.assertEqual(list(path.parent.glob(f".{path.name}.*.tmp")), [])


if __name__ == "__main__":
    unittest.main()
