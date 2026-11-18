"""Installer packaging contract: GNOME only bundles default entrypoints automatically."""
from pathlib import Path
import json
import os
import subprocess
import tempfile
import unittest
import zipfile

ROOT = Path(__file__).resolve().parent

# Deliberately model GNOME's pack defaults, not a naive zip of all source files.
FAKE_GNOME = """#!/usr/bin/env python3
import json, os, pathlib, sys, zipfile
args = sys.argv[1:]
if args[0] != 'pack':
    raise SystemExit('Unexpected install during --pack-only')
out = pathlib.Path(args[args.index('--out-dir') + 1])
source = pathlib.Path(args[-1])
metadata = json.loads((source / 'metadata.json').read_text())
names = ['extension.js', 'metadata.json']
names += [arg.split('=', 1)[1] for arg in args if arg.startswith('--extra-source=')]
for optional in ('prefs.js', 'stylesheet.css'):
    if (source / optional).exists() and optional not in names:
        names.append(optional)
omit = os.environ.get('OMIT_PACK_SOURCE')
if omit in names:
    names.remove(omit)
with zipfile.ZipFile(out / (metadata['uuid'] + '.shell-extension.zip'), 'w') as archive:
    for name in names:
        archive.write(source / name, name)
"""


class PackInstallerTests(unittest.TestCase):
    def setUp(self):
        self.sandbox = tempfile.TemporaryDirectory()
        self.addCleanup(self.sandbox.cleanup)
        self.root = Path(self.sandbox.name)
        self.repo = self.root / 'checkout'
        self.repo.mkdir()
        (self.repo / 'install.sh').write_bytes((ROOT / 'install.sh').read_bytes())
        required = [
            'dynwall', 'dynwall-settings', 'dynwall-settings.desktop',
            'dynwall_weather.py', '.env.example', 'dynwall_ding_menu.py',
            'systemd/dynwall.service', 'systemd/dynwall.timer',
            'systemd/dynwall-play.service',
        ]
        for name in required:
            path = self.repo / name
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text('fixture\n')
        extension = self.repo / 'extension'
        extension.mkdir()
        for name in (
            'extension.js', 'state.js', 'lifecycle.js', 'shader.js',
            'uniforms.js', 'presentation.js', 'living.js', 'seasonal.js',
            'weather.glsl', 'valley-fog.glsl',
        ):
            (extension / name).write_text('// stub\n')
        (extension / 'metadata.json').write_text(json.dumps({
            'uuid': 'dynwall@rucaradio', 'shell-version': ['50']}))
        self.bin = self.root / 'bin'
        self.bin.mkdir()
        cli = self.bin / 'gnome-extensions'
        cli.write_text(FAKE_GNOME)
        cli.chmod(0o755)

    def run_installer(self, **extra_env):
        env = dict(os.environ, PATH=f'{self.bin}:{os.environ["PATH"]}', **extra_env)
        return subprocess.run(
            ['bash', str(self.repo / 'install.sh'), '--pack-only'],
            capture_output=True, text=True, env=env, timeout=20)

    def test_pack_includes_all_imports_and_shaders(self):
        result = self.run_installer()
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        archive = self.repo / 'dist/dynwall@rucaradio.shell-extension.zip'
        self.assertTrue(archive.exists())
        with zipfile.ZipFile(archive) as bundle:
            expected = {p.name for p in (self.repo / 'extension').glob('*.js')}
            expected |= {p.name for p in (self.repo / 'extension').glob('*.glsl')}
            expected.add('metadata.json')
            self.assertTrue(expected.issubset(bundle.namelist()))
            self.assertIsNone(bundle.testzip())

    def test_missing_import_is_identified(self):
        result = self.run_installer(OMIT_PACK_SOURCE='seasonal.js')
        self.assertNotEqual(result.returncode, 0)
        self.assertIn('extension ZIP missing: seasonal.js', result.stderr)
        self.assertFalse((self.repo / 'dist').exists())


if __name__ == '__main__':
    unittest.main()
