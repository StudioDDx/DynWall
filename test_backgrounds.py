"""Built-in scene selection works offline through both refresh paths."""
from datetime import datetime
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from test_themes import app


class BackgroundTests(unittest.TestCase):
    def test_each_background_has_distinct_day_and_night_art(self):
        for name, style in [('ridges', 'hills'), ('alpine', 'alpine'),
                            ('dunes', 'dunes'), ('ocean', 'ocean'), ('sky', 'none')]:
            cfg = dict(app.DEFAULTS, background=name)
            day = app.background_spec(datetime(2026, 10, 31, 12), cfg, 'clear')
            night = app.background_spec(datetime(2026, 10, 31, 2), cfg, 'clear')
            self.assertEqual(day['landscape']['style'], style)
            self.assertNotEqual(day['gradient'], night['gradient'])
            self.assertEqual(day['celestial']['type'], 'sun')
            self.assertEqual(night['celestial']['type'], 'moon')
            self.assertEqual(day['mesh']['style'], 'none')

    def test_unknown_background_preserves_automatic_art(self):
        for name in ['auto', '../config', None, '']:
            self.assertIsNone(app.background_spec(datetime(2026, 10, 31),
                                                 {'background': name}, 'clear'))

    def test_selected_background_refresh_ignores_stale_art_and_network(self):
        with tempfile.TemporaryDirectory() as td:
            cache = Path(td)
            stale = cache / 'spec.json'
            stale.write_text(json.dumps({'spec': {'gradient': ['#ffffff', '#ffffff']}}))
            cfg = dict(app.DEFAULTS, background='alpine', theme='halloween')
            with patch.object(app, 'CACHE_DIR', cache), patch.object(app, 'SPEC_CACHE', stale), \
                 patch.object(app, 'load_config', return_value=cfg), \
                 patch.object(app, 'load_weather', return_value=None), \
                 patch.object(app, 'set_wallpaper', side_effect=AssertionError('wallpaper')), \
                 patch.object(app, 'llm_spec', side_effect=AssertionError('network')):
                self.assertEqual(app.main(['--refresh-scene']), 0)
                selected = app.get_spec('clear', cfg)
            published = json.loads((cache / 'scene.json').read_text())
            self.assertEqual(published['spec']['landscape']['style'], 'alpine')
            self.assertEqual(selected['landscape']['style'], 'alpine')

    def test_static_landscapes_are_visibly_distinct(self):
        with patch.object(app, 'W', 480), patch.object(app, 'H', 270):
            images = []
            for name in ['ridges', 'alpine', 'dunes', 'ocean']:
                spec = app.background_spec(datetime(2026, 10, 31, 12),
                                           dict(app.DEFAULTS, background=name), 'clear')
                image = app.build_landscape(spec, [app.hex_rgb(c) for c in spec['gradient']])
                self.assertIsNone(image.crop((0, 0, 480, 140)).getbbox())
                self.assertIsNotNone(image.crop((0, 230, 480, 270)).getbbox())
                images.append(image.tobytes())
            self.assertEqual(len(set(images)), 4)
