"""Native slideshow writing and service-rendering regressions."""
import importlib.machinery
import importlib.util
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
import xml.etree.ElementTree as ET

from PIL import Image

from dynwall_slideshow import write_slideshow

ROOT = Path(__file__).resolve().parent


def load_cli():
    loader = importlib.machinery.SourceFileLoader("dynwall_service_tests", str(ROOT / "dynwall"))
    spec = importlib.util.spec_from_loader(loader.name, loader)
    module = importlib.util.module_from_spec(spec)
    loader.exec_module(module)
    return module


class SlideshowTests(unittest.TestCase):
    def test_slideshow_requires_real_frames(self):
        with tempfile.TemporaryDirectory() as td:
            self.assertRaises(ValueError, write_slideshow,
                              Path(td) / "slideshow.xml",
                              [Path(td) / "missing.png"], 1.5)

    def test_slides_are_absolute_and_do_not_crossfade(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            frames = [root / "f000.png", root / "f001.png"]
            for frame in frames:
                Image.new("RGB", (8, 8), "#334455").save(frame)
            out = write_slideshow(root / "slideshow.xml", frames, 1.5)
            xml = ET.parse(out).getroot()
            self.assertEqual([x.tag for x in xml if x.tag != "starttime"],
                             ["static", "static"])
            self.assertEqual([x.findtext("file") for x in xml.findall("static")],
                             [str(x.resolve()) for x in frames])
            self.assertEqual([x.findtext("duration") for x in xml.findall("static")],
                             ["1.500", "1.500"])

    def test_smooth_slides_interpolate_and_wrap_without_jump(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            frames = [root / "first.png", root / "second.png"]
            for frame in frames:
                Image.new("RGB", (8, 8), "#556677").save(frame)
            xml = ET.parse(write_slideshow(root / "smooth.xml", frames, 1.5,
                                           smooth=True)).getroot()
            transitions = xml.findall("transition")
            self.assertEqual(len(transitions), 2)
            self.assertEqual([t.findtext("duration") for t in transitions],
                             ["1.500", "1.500"])
            self.assertEqual(transitions[-1].findtext("to"), str(frames[0].resolve()))
            self.assertTrue(all(s.findtext("duration") == "0.100" for s in xml.findall("static")))

    def test_render_mode_uses_new_generation_uri(self):
        cli = load_cli()
        with tempfile.TemporaryDirectory() as td:
            cache = Path(td)
            cfg = dict(cli.DEFAULTS, frames=2, frame_seconds=2.0,
                       width=8, height=8)
            calls = []
            def fake_frames(_spec, _n, _mesh, _terrain, output_dir):
                output_dir.mkdir()
                paths = [output_dir / f"f{i:03d}.png" for i in range(2)]
                for path in paths:
                    Image.new("RGB", (8, 8)).save(path)
                return paths
            with patch.object(cli, "CACHE_DIR", cache), \
                 patch.object(cli, "render_frames", side_effect=fake_frames), \
                 patch.object(cli, "set_wallpaper", side_effect=lambda p: calls.append(p)):
                cli.render_service_slideshow({}, cfg)
                cli.render_service_slideshow({}, cfg)
            self.assertEqual(len(calls), 2)
            self.assertNotEqual(calls[0], calls[1])
            self.assertTrue(calls[1].exists())
            self.assertEqual(len(list((cache / "slideshow").glob("gen-*"))), 2)


if __name__ == "__main__":
    unittest.main()
