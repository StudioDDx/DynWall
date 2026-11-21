#!/usr/bin/env bash
# Import a user-supplied Smokies Cinematic pack, enable it and refresh DynWall.
set -euo pipefail
REPO="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
if [ "$#" -ne 1 ] || [ ! -f "$1" ]; then
    echo "Usage: $0 /path/to/Smokies-Cinematic-DynWall-Pack.zip" >&2
    exit 2
fi
ARCHIVE="$(realpath "$1")"
python3 - "$REPO" "$ARCHIVE" <<'PY'
import json
import os
import sys
import tempfile
from pathlib import Path

repo = Path(sys.argv[1])
archive = Path(sys.argv[2])
sys.path.insert(0, str(repo))
from dynwall_living import import_pack, load_pack, pack_store

target = pack_store() / "smokies-cinematic"
if target.is_dir():
    load_pack(target)
else:
    result = import_pack(archive)
    if result.get("id") != "smokies-cinematic":
        raise SystemExit("Unexpected landscape pack ID: " + str(result.get("id")))
config = Path(os.environ.get("XDG_CONFIG_HOME", str(Path.home() / ".config"))) / "dynwall" / "config.json"
config.parent.mkdir(parents=True, exist_ok=True)
try:
    data = json.loads(config.read_text())
    if not isinstance(data, dict):
        data = {}
except (OSError, ValueError):
    data = {}
data.update({"enabled": True, "allow_animation": True,
             "landscape_enabled": True, "landscape_pack": "smokies-cinematic"})
fd, tmp = tempfile.mkstemp(prefix=".config-", dir=config.parent)
try:
    with os.fdopen(fd, "w", encoding="utf-8") as handle:
        json.dump(data, handle, indent=2)
        handle.write("\n")
        handle.flush()
        os.fsync(handle.fileno())
    os.chmod(tmp, 0o600)
    os.replace(tmp, config)
finally:
    if os.path.exists(tmp):
        os.unlink(tmp)
print("Selected smokies-cinematic landscape pack in", config)
PY
systemctl --user enable --now dynwall.timer
systemctl --user start dynwall.service
echo "Cinematic Smokies activated. Inspect: journalctl --user -u dynwall.service -n 30"
