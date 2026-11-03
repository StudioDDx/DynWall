"""CLI and settings regressions; all desktop/network side effects isolated."""
import importlib.machinery
import json
import os
import shutil
from pathlib import Path
import subprocess
import sys
import tempfile
import time
import types
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parent


class CliTests(unittest.TestCase):
    def test_master_off_prevents_timer_run_from_touching_wallpaper(self):
        module = importlib.machinery.SourceFileLoader(
            "dynwall_disabled_test", str(ROOT / "dynwall")).load_module()
        with patch.object(module, "load_config", return_value=dict(module.DEFAULTS, enabled=False)), \
             patch.object(module, "set_wallpaper", side_effect=AssertionError("wallpaper changed")), \
             patch.object(module, "write_scene", side_effect=AssertionError("scene changed")):
            self.assertEqual(module.main([]), 0)

    def test_environment_key_takes_precedence_over_saved_key(self):
        module = importlib.machinery.SourceFileLoader(
            "dynwall_env_config_test", str(ROOT / "dynwall")).load_module()
        with tempfile.TemporaryDirectory() as td:
            path = Path(td) / "config.json"
            path.write_text(json.dumps({"provider": "openai", "api_key": "saved-test-key"}))
            with patch.object(module, "CONFIG_FILE", path), \
                 patch.dict(os.environ, {"OPENAI_API_KEY": "environment-test-key"}):
                self.assertTrue(module.load_config()["api_key"] == "environment-test-key")

    def test_direct_art_generation_uses_environment_key_over_passed_config(self):
        module = importlib.machinery.SourceFileLoader(
            "dynwall_env_request_test", str(ROOT / "dynwall")).load_module()
        import requests
        from datetime import datetime
        scene = {"gradient": ["#123456", "#abcdef"]}
        response = types.SimpleNamespace(raise_for_status=lambda: None,
            json=lambda: {"choices": [{"message": {"content": json.dumps(scene)}}]})
        used_environment = []
        def post(_url, **kwargs):
            used_environment.append(kwargs["headers"]["Authorization"] == "Bearer environment-test-key")
            return response
        with patch.dict(os.environ, {"OPENAI_API_KEY": "environment-test-key"}), \
             patch.object(requests, "post", side_effect=post):
            result = module.llm_spec(datetime(2026, 10, 30), "clear",
                dict(module.DEFAULTS, api_key="saved-test-key"))
        self.assertEqual(result, scene)
        self.assertEqual(used_environment, [True])

    def test_invalid_numeric_settings_use_defaults(self):
        module = importlib.machinery.SourceFileLoader(
            "dynwall_config_test", str(ROOT / "dynwall")).load_module()
        invalid_numbers = [float("inf"), float("-inf"), float("nan"), True, 10 ** 400]
        with tempfile.TemporaryDirectory() as td:
            path = Path(td) / "config.json"
            for value in invalid_numbers:
                with self.subTest(value=value):
                    path.write_text(json.dumps({
                        "width": value, "height": value, "weather_fps": value,
                        "frames": value, "frame_seconds": value,
                    }))
                    with patch.object(module, "CONFIG_FILE", path):
                        cfg = module.load_config()
                    for field in ("width", "height", "weather_fps", "frames", "frame_seconds"):
                        expected = module.DEFAULTS[field]
                        if type(value) is int and field != "frame_seconds":
                            expected = {"width": 15360, "height": 15360, "weather_fps": 60, "frames": 120}[field]
                        self.assertEqual(cfg[field], expected, field)

    def test_explicit_zero_frame_count_clamps_to_one(self):
        module = importlib.machinery.SourceFileLoader("dynwall_zero_test", str(ROOT / "dynwall")).load_module()
        with tempfile.TemporaryDirectory() as td:
            cache = Path(td)
            cfg = dict(module.DEFAULTS, provider="none", width=64, height=32)
            with patch.object(module, "CACHE_DIR", cache), \
                 patch.object(module, "FRAMES_DIR", cache / "frames"), \
                 patch.object(module, "SPEC_CACHE", cache / "spec.json"), \
                 patch.object(module, "load_config", return_value=cfg), \
                 patch.object(module, "load_weather", return_value=None):
                self.assertEqual(module.main(["--animate", "0"]), 0)
            self.assertEqual(len(list((cache / "frames").glob("*.png"))), 1)

    def test_missing_topweather_does_not_start_a_second_weather_poller(self):
        module = importlib.machinery.SourceFileLoader("dynwall_cli_test", str(ROOT / "dynwall")).load_module()
        with tempfile.TemporaryDirectory() as td:
            cache = Path(td)
            cfg = dict(module.DEFAULTS, provider="none", width=64, height=32)
            with patch.object(module, "CACHE_DIR", cache), \
                 patch.object(module, "OUT_PNG", cache / "wall.png"), \
                 patch.object(module, "SPEC_CACHE", cache / "spec.json"), \
                 patch.object(module, "load_config", return_value=cfg), \
                 patch.object(module, "load_weather", return_value=None), \
                 patch.object(module, "get_weather", side_effect=AssertionError("second weather poller called")), \
                 patch.object(module.subprocess, "run", return_value=subprocess.CompletedProcess([], 0)):
                self.assertEqual(module.main([]), 0)
            self.assertIsNone(json.loads((cache / "scene.json").read_text())["weather"])

    def test_refresh_scene_uses_topweather_without_network_or_wallpaper_changes(self):
        with tempfile.TemporaryDirectory() as td:
            home = Path(td)
            cache = home / "cache"
            config = home / "config" / "dynwall"
            config.mkdir(parents=True)
            (config / "config.json").write_text(json.dumps({
                "allow_network": False, "allow_animation": True,
                "weather_fps": 45, "weather_quality": "high",
                "seasonal_effects": False,
                "landscape_enabled": False,
            }))
            (cache / "topweather").mkdir(parents=True)
            (cache / "topweather/current.json").write_text(json.dumps({
                "schemaVersion": 1, "fetchedAt": int(time.time() * 1000),
                "provider": "wttr", "location": "Test", "unit": "c",
                "latitude": None, "longitude": None,
                "current": {"desc": "Light rain", "temp": 14,
                            "isNight": False, "cloudCover": 85, "rain": 0.8,
                            "windSpeedKmh": 12, "windDirection": 240},
            }))
            (cache / "dynwall").mkdir()
            (cache / "dynwall/spec.json").write_text(json.dumps({
                "spec": {"gradient": ["#123456", "#abcdef"], "stars": 0},
            }))
            env = dict(os.environ, HOME=td, XDG_CACHE_HOME=str(cache),
                       XDG_CONFIG_HOME=str(home / "config"),
                       DBUS_SESSION_BUS_ADDRESS="unix:path=/nonexistent-dynwall-test")
            result = subprocess.run([sys.executable, str(ROOT / "dynwall"),
                                     "--refresh-scene"], env=env, text=True,
                                    capture_output=True, timeout=10)
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertTrue((cache / "dynwall/scene.json").exists(), "CLI must publish a GPU scene")
            scene = json.loads((cache / "dynwall/scene.json").read_text())
            self.assertEqual(scene["weather"]["current"]["cloudCover"], 85)
            self.assertEqual(scene["spec"]["gradient"], ["#123456", "#abcdef"])
            self.assertEqual(scene["spec"]["landscape"]["style"], "none")
            self.assertEqual(scene["renderer"], {"enabled": True, "fps": 45, "quality": "high", "seasonalEffects": False})
            self.assertFalse((cache / "dynwall/wall.png").exists())
            self.assertNotIn("gsettings", result.stderr)

    def test_legacy_player_exits_with_migration_instructions(self):
        with tempfile.TemporaryDirectory() as td:
            result = subprocess.run([sys.executable, str(ROOT / "dynwall"), "--play"],
                                    env=dict(os.environ, HOME=td), capture_output=True,
                                    text=True, timeout=5)
            self.assertEqual(result.returncode, 2)
            self.assertIn("gnome-extensions enable dynwall@rucaradio", result.stderr)


class SettingsTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.settings = importlib.machinery.SourceFileLoader(
            "dynwall_settings_test", str(ROOT / "dynwall-settings")).load_module()

    def test_background_choices_round_trip_through_settings_and_cli(self):
        settings = self.settings
        module = importlib.machinery.SourceFileLoader(
            "dynwall_background_config_test", str(ROOT / "dynwall")).load_module()
        with tempfile.TemporaryDirectory() as td:
            path = Path(td) / "config.json"
            with patch.object(settings, "CONFIG_DIR", td), patch.object(settings, "CONFIG_PATH", str(path)), \
                 patch.object(module, "CONFIG_FILE", path):
                for background in settings.BACKGROUNDS:
                    settings.save_config(dict(settings.DEFAULTS, background=background))
                    self.assertEqual(settings.load_config()['background'], background)
                    self.assertEqual(module.load_config()['background'], background)
                path.write_text(json.dumps({'background': 'unknown'}))
                self.assertEqual(settings.load_config()['background'], 'auto')

    def test_seasonal_effects_can_be_saved_and_loaded(self):
        settings = self.settings
        self.assertIs(settings.DEFAULTS.get("seasonal_effects"), True)
        with tempfile.TemporaryDirectory() as td:
            path = Path(td) / "config.json"
            with patch.object(settings, "CONFIG_DIR", td), \
                 patch.object(settings, "CONFIG_PATH", str(path)):
                settings.save_config(dict(settings.DEFAULTS, seasonal_effects=False))
                self.assertIs(settings.load_config()["seasonal_effects"], False)

    def test_landscape_switch_can_be_saved_and_loaded(self):
        settings = self.settings
        self.assertIs(settings.DEFAULTS.get("landscape_enabled"), True)
        with tempfile.TemporaryDirectory() as td:
            path = Path(td) / "config.json"
            with patch.object(settings, "CONFIG_DIR", td), patch.object(settings, "CONFIG_PATH", str(path)):
                settings.save_config(dict(settings.DEFAULTS, landscape_enabled=False))
                self.assertIs(settings.load_config()["landscape_enabled"], False)

    def test_master_switch_can_be_saved_and_loaded(self):
        settings = self.settings
        self.assertIs(settings.DEFAULTS.get("enabled"), True)
        with tempfile.TemporaryDirectory() as td:
            path = Path(td) / "config.json"
            with patch.object(settings, "CONFIG_DIR", td), patch.object(settings, "CONFIG_PATH", str(path)):
                settings.save_config(dict(settings.DEFAULTS, enabled=False))
                self.assertIs(settings.load_config()["enabled"], False)

    def test_master_off_stops_dynwall_and_restores_ubuntu_wallpaper_defaults(self):
        calls = []
        def run(cmd, **kwargs):
            calls.append(cmd)
            return subprocess.CompletedProcess(cmd, 0, "", "")
        with patch.object(self.settings.subprocess, "run", run):
            ok, errors = self.settings.sync_dynwall_state(False)
        self.assertTrue(ok, errors)
        self.assertEqual(calls, [
            ["systemctl", "--user", "disable", "--now", "dynwall.timer"],
            ["gnome-extensions", "disable", "dynwall@rucaradio"],
            ["/usr/bin/gsettings", "reset", "org.gnome.desktop.background", "picture-uri"],
            ["/usr/bin/gsettings", "reset", "org.gnome.desktop.background", "picture-uri-dark"],
            ["/usr/bin/gsettings", "reset", "org.gnome.desktop.background", "picture-options"],
        ])

    def test_master_on_restores_cached_wallpaper_and_services(self):
        calls = []
        def run(cmd, **kwargs):
            calls.append(cmd)
            return subprocess.CompletedProcess(cmd, 0, "", "")
        with tempfile.TemporaryDirectory() as td:
            wall = Path(td) / "wall.png"
            wall.write_bytes(b"fixture")
            with patch.object(self.settings.subprocess, "run", run), \
                 patch.object(self.settings, "WALLPAPER_PATH", wall):
                ok, errors = self.settings.sync_dynwall_state(True)
        self.assertTrue(ok, errors)
        uri = wall.resolve().as_uri()
        self.assertEqual(calls, [
            ["systemctl", "--user", "enable", "--now", "dynwall.timer"],
            ["gnome-extensions", "enable", "dynwall@rucaradio"],
            ["/usr/bin/gsettings", "set", "org.gnome.desktop.background", "picture-uri", uri],
            ["/usr/bin/gsettings", "set", "org.gnome.desktop.background", "picture-uri-dark", uri],
            ["/usr/bin/gsettings", "set", "org.gnome.desktop.background", "picture-options", "spanned"],
        ])

    def test_save_publishes_complete_private_config_atomically(self):
        settings = self.settings
        with tempfile.TemporaryDirectory() as td:
            path = Path(td) / "config.json"
            original = '{"prompt":"old sky"}\n'
            path.write_text(original)
            cfg = dict(settings.DEFAULTS, prompt="Evening sky", api_key="test-key")
            replace = os.replace
            published = []

            def check_replace(source, destination):
                self.assertEqual(path.read_text(), original)
                self.assertEqual(json.loads(Path(source).read_text()), cfg)
                self.assertEqual(Path(source).stat().st_mode & 0o777, 0o600)
                self.assertEqual(Path(source).parent, path.parent)
                published.append(True)
                replace(source, destination)

            with patch.object(settings, "CONFIG_DIR", td), \
                 patch.object(settings, "CONFIG_PATH", str(path)), \
                 patch.object(settings.os, "replace", side_effect=check_replace):
                settings.save_config(cfg)

            self.assertEqual(published, [True])
            self.assertEqual(json.loads(path.read_text()), cfg)
            self.assertEqual(path.stat().st_mode & 0o777, 0o600)
            self.assertEqual(list(Path(td).iterdir()), [path])

    def test_failed_save_preserves_previous_config(self):
        settings = self.settings
        for operation in ("fsync", "replace"):
            with self.subTest(operation=operation), tempfile.TemporaryDirectory() as td:
                path = Path(td) / "config.json"
                original = '{"prompt":"old sky"}\n'
                path.write_text(original)
                with patch.object(settings, "CONFIG_DIR", td), \
                     patch.object(settings, "CONFIG_PATH", str(path)), \
                     patch.object(settings.os, operation, side_effect=OSError("disk failure")):
                    with self.assertRaisesRegex(OSError, "disk failure"):
                        settings.save_config(dict(settings.DEFAULTS))
                self.assertEqual(path.read_text(), original)
                self.assertEqual(list(Path(td).iterdir()), [path])

    def test_invalid_config_does_not_damage_previous_save(self):
        settings = self.settings
        for invalid in ({"prompt": object()}, {"frame_seconds": float("nan")}):
            with self.subTest(invalid=invalid), tempfile.TemporaryDirectory() as td:
                path = Path(td) / "config.json"
                original = '{"prompt":"old sky"}\n'
                path.write_text(original)
                with patch.object(settings, "CONFIG_DIR", td), \
                     patch.object(settings, "CONFIG_PATH", str(path)):
                    with self.assertRaises((TypeError, ValueError)):
                        settings.save_config(invalid)
                self.assertEqual(path.read_text(), original)
                self.assertEqual(list(Path(td).iterdir()), [path])

    def test_animation_save_never_enables_legacy_player(self):
        calls = []
        def run(cmd, **kwargs):
            calls.append(cmd)
            return subprocess.CompletedProcess(cmd, 0)
        with patch.object(self.settings.subprocess, "run", run):
            self.assertTrue(self.settings.sync_play_service(True))
        self.assertEqual(calls, [["systemctl", "--user", "disable", "--now", "dynwall-play.service"]])

    def test_quality_and_fps_settings_round_trip_and_clamp(self):
        with tempfile.TemporaryDirectory() as td:
            cfgpath = Path(td) / "config.json"
            cfgpath.write_text(json.dumps({"weather_fps": 500, "weather_quality": "bad"}))
            with patch.object(self.settings, "CONFIG_PATH", str(cfgpath)):
                cfg = self.settings.load_config()
            self.assertIn("weather_fps", cfg)
            self.assertEqual(cfg["weather_fps"], 60)
            self.assertEqual(cfg["weather_quality"], "balanced")

    def test_numeric_config_stays_within_supported_ranges(self):
        settings = self.settings
        cases = (
            ({"width": True, "weather_fps": True}, {"width": 3840, "weather_fps": 30}),
            ({"frame_seconds": float("nan")}, {"frame_seconds": 1.5}),
            ({"frame_seconds": float("inf")}, {"frame_seconds": 1.5}),
            ({"frame_seconds": 2}, {"frame_seconds": 2.0}),
            ({"width": 99999, "height": 99999}, {"width": 15360, "height": 15360}),
        )
        with tempfile.TemporaryDirectory() as td:
            path = Path(td) / "config.json"
            for raw, expected in cases:
                with self.subTest(raw=raw):
                    path.write_text(json.dumps(raw))
                    with patch.object(settings, "CONFIG_PATH", str(path)):
                        cfg = settings.load_config()
                    for field, value in expected.items():
                        self.assertEqual(cfg[field], value, field)

    def test_save_and_regenerate_starts_only_one_scene_writer(self):
        settings = self.settings
        window = types.SimpleNamespace(_collect=lambda: dict(settings.DEFAULTS), _toast=lambda *_: None)
        window._do_save = types.MethodType(settings.SettingsWindow._do_save, window)
        button = types.SimpleNamespace(set_sensitive=lambda *_: None)
        commands = []
        with tempfile.TemporaryDirectory() as td, \
             patch.object(settings, "CONFIG_DIR", td), \
             patch.object(settings, "CONFIG_PATH", str(Path(td) / "config.json")), \
             patch.object(settings, "sync_play_service", return_value=True), \
             patch.object(settings, "sync_dynwall_state", return_value=(True, [])), \
             patch.object(settings.subprocess, "Popen", side_effect=lambda cmd, **kw: commands.append(cmd)), \
             patch.object(settings.GLib, "timeout_add_seconds", return_value=1):
            settings.SettingsWindow._on_save_and_regen(window, button)
        self.assertEqual(commands, [[settings.DYNWALL_CMD]])


class InstallerTests(unittest.TestCase):
    def test_missing_uniform_module_fails_before_mutating_installation(self):
        with tempfile.TemporaryDirectory() as td:
            home = Path(td) / 'home'
            home.mkdir()
            package = Path(td) / 'package'
            shutil.copytree(ROOT, package, ignore=shutil.ignore_patterns('.git', '__pycache__'))
            (package / 'extension/uniforms.js').unlink()
            bindir = Path(td) / 'bin'
            bindir.mkdir()
            for name in ('systemctl', 'gnome-extensions', 'update-desktop-database'):
                stub = bindir / name
                stub.write_text('#!/bin/sh\nexit 0\n')
                stub.chmod(0o755)
            result = subprocess.run(['bash', str(package / 'install.sh'), '--no-render'],
                                    env=dict(os.environ, HOME=str(home), PATH=f'{bindir}:/usr/bin:/bin'),
                                    capture_output=True, text=True, timeout=10)
            self.assertNotEqual(result.returncode, 0, 'installer accepted a missing runtime module')
            self.assertFalse((home / '.local').exists())

    def test_incomplete_package_fails_before_mutating_installation(self):
        with tempfile.TemporaryDirectory() as td:
            home = Path(td) / "home"
            home.mkdir()
            package = Path(td) / "package"
            package.mkdir()
            shutil.copy2(ROOT / "install.sh", package / "install.sh")
            result = subprocess.run(["bash", str(package / "install.sh"), "--no-render"],
                                    env=dict(os.environ, HOME=str(home)),
                                    capture_output=True, text=True, timeout=10)
            self.assertNotEqual(result.returncode, 0)
            self.assertFalse((home / ".local").exists(), "broken package mutated installation")

    def test_install_stages_gpu_extension_but_does_not_enable_it_implicitly(self):
        with tempfile.TemporaryDirectory() as td:
            home = Path(td)
            bindir = home / "bin"
            bindir.mkdir()
            log = home / "commands.log"
            for name in ("systemctl", "gnome-extensions", "update-desktop-database"):
                stub = bindir / name
                stub.write_text('#!/bin/sh\nprintf "%s\\n" "' + name + ' $*" >> "$TEST_LOG"\n')
                stub.chmod(0o755)
            result = subprocess.run(["bash", str(ROOT / "install.sh"), "--no-render"],
                env=dict(os.environ, HOME=td, TEST_LOG=str(log),
                         PATH=f"{bindir}:/usr/bin:/bin"),
                capture_output=True, text=True, timeout=15)
            self.assertEqual(result.returncode, 0, result.stderr)
            installed = home / ".local/share/gnome-shell/extensions/dynwall@rucaradio"
            self.assertTrue((installed / "metadata.json").exists())
            commands = log.read_text()
            self.assertIn("systemctl --user disable --now dynwall-play.service", commands)
            self.assertNotIn("gnome-extensions enable", commands)
            self.assertFalse((home / ".cache/dynwall/wall.png").exists())

    def test_install_preserves_a_disabled_master_setting(self):
        with tempfile.TemporaryDirectory() as td:
            home = Path(td)
            config = home / ".config/dynwall"
            config.mkdir(parents=True)
            (config / "config.json").write_text('{"enabled": false}\n')
            bindir = home / "bin"
            bindir.mkdir()
            log = home / "commands.log"
            for name in ("systemctl", "gnome-extensions", "update-desktop-database"):
                stub = bindir / name
                stub.write_text('#!/bin/sh\nprintf "%s\\n" "' + name + ' $*" >> "$TEST_LOG"\n')
                stub.chmod(0o755)
            result = subprocess.run(["bash", str(ROOT / "install.sh"), "--no-render"],
                env=dict(os.environ, HOME=td, TEST_LOG=str(log),
                         PATH=f"{bindir}:/usr/bin:/bin"),
                capture_output=True, text=True, timeout=15)
            self.assertEqual(result.returncode, 0, result.stderr)
            commands = log.read_text()
            self.assertIn("systemctl --user disable --now dynwall.timer", commands)
            self.assertNotIn("systemctl --user enable --now dynwall.timer", commands)


if __name__ == "__main__":
    unittest.main()
