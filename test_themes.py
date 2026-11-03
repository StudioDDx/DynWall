"""Local theme behavior, with desktop and network boundaries isolated."""
import importlib.machinery
import json
from datetime import datetime
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parent
app = importlib.machinery.SourceFileLoader('dynwall_theme_tests', str(ROOT / 'dynwall')).load_module()


class ThemeTests(unittest.TestCase):
    def config(self, **changes):
        return dict(app.DEFAULTS, theme='halloween', theme_until='2026-11-01', **changes)

    def test_local_theme_bypasses_network_and_old_art_cache(self):
        with tempfile.TemporaryDirectory() as td:
            cache = Path(td) / 'spec.json'
            cache.write_text(json.dumps({'spec': {'gradient': ['#ffffff', '#ffffff']}}))
            with patch.object(app, 'SPEC_CACHE', cache), patch.object(app, 'datetime') as clock, \
                 patch.object(app, 'llm_spec', side_effect=AssertionError('theme must work offline')):
                clock.now.return_value = datetime(2026, 10, 31, 23, 59)
                spec = app.get_spec('Cloudy', self.config())
            self.assertEqual(spec['title'], 'Witching Hour')
            self.assertEqual(spec['gradient'][0], '#080611')
            self.assertEqual(spec['mesh']['style'], 'none')

    def test_theme_expires_at_local_midnight(self):
        self.assertEqual(app.theme_spec(datetime(2026, 10, 31, 23, 59), self.config())['title'], 'Witching Hour')
        self.assertIsNone(app.theme_spec(datetime(2026, 11, 1), self.config()))

    def test_invalid_theme_or_expiry_uses_normal_art(self):
        for changes in [{'theme': '../config'}, {'theme_until': 'invalid'}, {'theme_until': None}]:
            cfg = self.config()
            cfg.update(changes)
            self.assertIsNone(app.theme_spec(datetime(2026, 10, 30), cfg))

    def test_refresh_publishes_theme_without_network_or_wallpaper_changes(self):
        with tempfile.TemporaryDirectory() as td:
            cache = Path(td)
            with patch.object(app, 'CACHE_DIR', cache), \
                 patch.object(app, 'load_config', return_value=self.config()), \
                 patch.object(app, 'datetime') as clock, \
                 patch.object(app, 'load_weather', return_value=None), \
                 patch.object(app, 'llm_spec', side_effect=AssertionError('network')), \
                 patch.object(app, 'set_wallpaper', side_effect=AssertionError('wallpaper reload')):
                clock.now.return_value = datetime(2026, 10, 30)
                self.assertEqual(app.main(['--refresh-scene']), 0)
            self.assertEqual(json.loads((cache / 'scene.json').read_text())['spec']['title'], 'Witching Hour')

    def test_config_retains_theme_selection(self):
        with tempfile.TemporaryDirectory() as td:
            config = Path(td) / 'config.json'
            config.write_text(json.dumps(self.config()))
            with patch.object(app, 'CONFIG_FILE', config):
                loaded = app.load_config()
            self.assertEqual(loaded['theme'], 'halloween')
            self.assertEqual(loaded['theme_until'], '2026-11-01')

    def test_daytime_has_its_own_palette_and_sun(self):
        spec = app.theme_spec(datetime(2026, 10, 30, 12), self.config())
        self.assertEqual(spec['title'], 'Hollow Harvest')
        self.assertEqual(spec['celestial']['type'], 'sun')
        self.assertEqual(spec['stars'], 0)
        night = app.theme_spec(datetime(2026, 10, 30, 2), self.config())
        self.assertNotEqual(spec['gradient'], night['gradient'])

    def test_observed_daylight_overrides_clock_fallback(self):
        early = datetime(2026, 10, 30, 7)
        late = datetime(2026, 10, 30, 19)
        self.assertEqual(app.theme_spec(early, self.config(), {'current': {'isNight': True}})['title'], 'Witching Hour')
        self.assertEqual(app.theme_spec(late, self.config(), {'current': {'isNight': False}})['title'], 'Hollow Harvest')

    def test_missing_daylight_observation_uses_local_clock(self):
        for hour, title in [(6, 'Witching Hour'), (7, 'Hollow Harvest'),
                            (17, 'Hollow Harvest'), (18, 'Witching Hour')]:
            self.assertEqual(app.theme_spec(datetime(2026, 10, 30, hour), self.config(),
                                           {'current': {}})['title'], title)
