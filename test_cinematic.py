"""Tests for opt-in cinematic wallpaper animation, independent of a GNOME session."""
import importlib.machinery
import importlib.util
from datetime import datetime
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
from PIL import Image, ImageChops

from dynwall_cinematic import build_frames

ROOT = Path(__file__).resolve().parent


def load_cli():
    loader = importlib.machinery.SourceFileLoader("dynwall_cinematic_contract", str(ROOT / "dynwall"))
    spec = importlib.util.spec_from_loader(loader.name, loader)
    module = importlib.util.module_from_spec(spec)
    loader.exec_module(module)
    return module


class CinematicTests(unittest.TestCase):
    def test_frames_are_distinct_and_well_formed(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            source = root / "source.png"
            Image.new("RGBA", (180, 100), (40, 85, 116, 254)).save(source)
            files = build_frames(source, root / "render", (180, 100), 6,
                                 clock=datetime(2026, 9, 18, 16),
                                 weather={"current": {"cloudCover": 90}})
            self.assertEqual(len(files), 6)
            with Image.open(files[0]) as first, Image.open(files[2]) as other:
                self.assertEqual(first.size, (180, 100))
                self.assertIsNotNone(ImageChops.difference(first, other).getbbox())

    def test_bad_source_or_count_does_not_publish_frames(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            with self.assertRaises(ValueError):
                build_frames(root / "missing.png", root / "output", (64, 64), 0)
            self.assertFalse((root / "output").exists())

    def test_cinematic_pack_uses_service_renderer(self):
        cli = load_cli()
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            art = root / "foreground.png"
            Image.new("RGBA", (100, 60), (25, 90, 45, 254)).save(art)
            cfg = dict(cli.DEFAULTS, landscape_pack="smokies-cinematic",
                       landscape_enabled=True, frames=2, frame_seconds=2.0)
            from unittest.mock import MagicMock
            fake_pack = {"foreground": str(art), "id": "smokies-cinematic"}
            with patch.object(cli, "CACHE_DIR", root), \
                 patch.object(cli, "W", 100), patch.object(cli, "H", 60), \
                 patch("dynwall_living.load_pack", return_value=fake_pack), \
                 patch("dynwall_living.pack_directory", return_value=root), \
                 patch.object(cli, "set_wallpaper") as update:
                cli.render_service_slideshow({}, cfg)
            update.assert_called_once()
            out = update.call_args.args[0]
            self.assertTrue(out.exists())
            self.assertEqual(len(list(out.parent.glob("f*.png"))), 2)


if __name__ == "__main__":
    unittest.main()
