"""Layered landscape importer regressions; no GNOME session required."""
import json
from pathlib import Path
import tempfile
import unittest
from PIL import Image
from dynwall_living import load_pack, import_pack, export_pack, validate_pack_manifest


class LayeredPackTests(unittest.TestCase):
    def make_pack(self, root):
        root.mkdir(parents=True, exist_ok=True)
        Image.new('RGBA', (64, 40), (30, 70, 60, 255)).save(root/'foreground.png')
        names = []
        for i in range(4):
            path = root/f'layer-{i}.png'
            Image.new('RGBA', (64, 40), (20+i, 40, 60, 0)).save(path)
            names.append(path.name)
        manifest = {'schemaVersion': 1, 'id': 'winter', 'name': 'Winter Smokies',
                    'horizon': .72, 'foreground': 'foreground.png', 'layers': names}
        (root/'manifest.json').write_text(json.dumps(manifest))
        return manifest

    def test_round_trip_keeps_depth_layers(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            self.make_pack(root/'source')
            original = load_pack(root/'source')
            self.assertEqual(len(original['layers']), 4)
            installed = import_pack(root/'source', root/'installed')
            self.assertEqual(len(installed['layers']), 4)
            target = root/'out.zip'
            export_pack(installed, target)
            restored = import_pack(target, root/'restored')
            self.assertEqual(len(restored['layers']), 4)
            for path in restored['layers']:
                with Image.open(path) as image:
                    self.assertEqual(image.size, (64, 40))
                    self.assertEqual(image.mode, 'RGBA')

    def test_duplicate_layers_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            manifest = self.make_pack(root)
            manifest['layers'][1] = manifest['layers'][0]
            with self.assertRaises(ValueError):
                validate_pack_manifest(manifest)

    def test_layer_geometry_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            self.make_pack(root)
            Image.new('RGBA', (32, 40)).save(root/'layer-2.png')
            with self.assertRaises(ValueError):
                load_pack(root)

    def test_legacy_pack_still_supported(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            manifest = self.make_pack(root)
            del manifest['layers']
            (root/'manifest.json').write_text(json.dumps(manifest))
            self.assertNotIn('layers', load_pack(root))


if __name__ == '__main__':
    unittest.main()
