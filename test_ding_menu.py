"""Managed DING desktop-menu integration contracts."""

import importlib
import tempfile
import unittest
from pathlib import Path


class DingMenuInstallerTests(unittest.TestCase):
    def setUp(self):
        self.module = importlib.import_module("dynwall_ding_menu")

    def _source(self, root: Path) -> Path:
        source = root / "system" / "ding@rastersoft.com"
        (source / "app").mkdir(parents=True)
        (source / "metadata.json").write_text('{"uuid":"ding@rastersoft.com","version":105}')
        (source / "extension.js").write_text("// fixture\n")
        (source / "app" / "desktopManager.js").write_text(
            "        this._menu.add(this._changeBackgroundMenuItem);\n\n"
            "        this._menu.add(new Gtk.SeparatorMenuItem());\n"
        )
        return source

    def test_install_adds_one_settings_item_and_is_idempotent(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            source = self._source(root)
            target = root / "user" / "ding@rastersoft.com"
            self.module.install_menu(source, target)
            first = (target / "app" / "desktopManager.js").read_text()
            self.assertEqual(first.count("Dynwall Settings"), 1)
            self.assertIn("dynwall-settings.desktop", first)
            self.assertTrue((target / self.module.MARKER).exists())
            self.module.install_menu(source, target)
            self.assertEqual((target / "app" / "desktopManager.js").read_text(), first)

    def test_install_refuses_an_unmanaged_user_extension(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            source = self._source(root)
            target = root / "user" / "ding@rastersoft.com"
            target.mkdir(parents=True)
            (target / "user-file").write_text("keep")
            with self.assertRaisesRegex(RuntimeError, "unmanaged"):
                self.module.install_menu(source, target)
            self.assertEqual((target / "user-file").read_text(), "keep")

    def test_unknown_ding_source_is_rejected_before_target_creation(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            source = root / "system" / "ding@rastersoft.com"
            (source / "app").mkdir(parents=True)
            (source / "app" / "desktopManager.js").write_text("different release")
            target = root / "user" / "ding@rastersoft.com"
            with self.assertRaisesRegex(RuntimeError, "anchor"):
                self.module.install_menu(source, target)
            self.assertFalse(target.exists())


if __name__ == "__main__":
    unittest.main()
