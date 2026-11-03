"""Deterministic offline art direction shared by render previews."""
import importlib.machinery
import importlib.util
import json
from datetime import datetime
from pathlib import Path

loader = importlib.machinery.SourceFileLoader("dynwall_art_fixtures", str(Path(__file__).resolve().parents[1] / "dynwall"))
spec = importlib.util.spec_from_loader(loader.name, loader)
module = importlib.util.module_from_spec(spec)
loader.exec_module(module)
print(json.dumps([
    {"name": name, "spec": module.fallback_spec(datetime(2026, 10, 30, hour), "clear")}
    for name, hour in [("dawn", 7), ("fallback-day", 12), ("golden-hour", 18), ("night-fallback", 2)]
] + [
    {"name": f"{name}-{phase}", "spec": module.background_spec(
        datetime(2026, 10, 31, hour), dict(module.DEFAULTS, background=name), "clear")}
    for name in ["ridges", "alpine", "dunes", "ocean", "sky"]
    for phase, hour in [("day", 12), ("dusk", 18), ("night", 2)]
]))
