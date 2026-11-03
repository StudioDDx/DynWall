#!/usr/bin/python3
"""Install a managed user-level DING copy with a Dynwall Settings menu item."""

import argparse
import json
import os
import shutil
import tempfile
from pathlib import Path


MARKER = ".dynwall-menu.json"
ANCHOR = (
    "        this._menu.add(this._changeBackgroundMenuItem);\n\n"
    "        this._menu.add(new Gtk.SeparatorMenuItem());\n"
)
ITEM = """        this._menu.add(this._changeBackgroundMenuItem);

        this._dynwallSettingsMenuItem = new Gtk.MenuItem({label: 'Dynwall Settings'});
        this._dynwallSettingsMenuItem.connect('activate', () => {
            const desktopFile = GioUnix.DesktopAppInfo.new('dynwall-settings.desktop');
            if (desktopFile) {
                const context = Gdk.Display.get_default().get_app_launch_context();
                context.set_timestamp(Gtk.get_current_event_time());
                desktopFile.launch([], context);
            }
        });
        this._menu.add(this._dynwallSettingsMenuItem);

        this._menu.add(new Gtk.SeparatorMenuItem());
"""


def _patch(source: str) -> str:
    if "Dynwall Settings" in source:
        return source
    if source.count(ANCHOR) != 1:
        raise RuntimeError("DING desktop menu anchor was not found exactly once")
    return source.replace(ANCHOR, ITEM)


def install_menu(source: Path, target: Path) -> None:
    source, target = Path(source), Path(target)
    manager = source / "app" / "desktopManager.js"
    if not manager.is_file():
        raise RuntimeError(f"DING source is incomplete: {manager}")
    patched = _patch(manager.read_text(encoding="utf-8"))
    if target.exists() and not (target / MARKER).is_file():
        raise RuntimeError(f"refusing to replace unmanaged user extension: {target}")

    target.parent.mkdir(parents=True, exist_ok=True)
    stage = Path(tempfile.mkdtemp(prefix=f".{target.name}.", dir=target.parent))
    backup = target.with_name(f".{target.name}.previous")
    try:
        shutil.copytree(source, stage, dirs_exist_ok=True, symlinks=True)
        (stage / "app" / "desktopManager.js").write_text(patched, encoding="utf-8")
        metadata = json.loads((source / "metadata.json").read_text(encoding="utf-8"))
        (stage / MARKER).write_text(json.dumps({
            "managedBy": "dynwall", "source": str(source), "version": metadata.get("version"),
        }, sort_keys=True) + "\n", encoding="utf-8")
        if backup.exists():
            shutil.rmtree(backup)
        if target.exists():
            os.replace(target, backup)
        os.replace(stage, target)
        if backup.exists():
            shutil.rmtree(backup)
    except Exception:
        if target.exists() and backup.exists():
            shutil.rmtree(target)
        if not target.exists() and backup.exists():
            os.replace(backup, target)
        if stage.exists():
            shutil.rmtree(stage)
        raise


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--source", type=Path, required=True)
    parser.add_argument("--target", type=Path, required=True)
    args = parser.parse_args()
    install_menu(args.source, args.target)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
