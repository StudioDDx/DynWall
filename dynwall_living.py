"""Local scene configuration, landscape packs and deterministic selections.

No networking, desktop mutation or credentials are needed. Config helpers return
copies. ``now`` is epoch seconds. Pack directories/archives contain just a bounded
manifest and PNG foreground; imported opaque photographs are cut at their marked
horizon so the native animated sky remains visible.
"""
from __future__ import annotations

import copy
from datetime import datetime, timedelta
import json
import math
import os
from pathlib import Path, PurePosixPath
import re
import shutil
import stat
import tempfile
import time
import zipfile
from PIL import Image

BACKGROUNDS = ('auto', 'ridges', 'alpine', 'dunes', 'ocean', 'sky')
DEFAULT_CUSTOMIZATION = {'horizon': .8, 'terrain_scale': 1., 'mist': .5,
                         'warmth': 0., 'darkness': 0., 'animation_intensity': 1.}
RANGES = {'horizon': (.5, .95), 'terrain_scale': (.5, 2.), 'mist': (0., 1.),
          'warmth': (-1., 1.), 'darkness': (0., 1.), 'animation_intensity': (0., 2.)}
PACK_ID = re.compile(r'^[a-z0-9][a-z0-9_-]{0,63}$')
MAX_MANIFEST_BYTES = 16384
MAX_ASSET_BYTES = 32 * 1024 * 1024
MAX_PIXELS = 32 * 1024 * 1024
MAX_COLLECTION = 24


def _number(value, default, low, high):
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return default
    try:
        value = float(value)
    except OverflowError:
        return default
    return max(low, min(high, value)) if math.isfinite(value) else default


def _customization(raw):
    raw = raw if isinstance(raw, dict) else {}
    return {key: _number(raw.get(key), default, *RANGES[key])
            for key, default in DEFAULT_CUSTOMIZATION.items()}


def _pack_id(value):
    return value if isinstance(value, str) and PACK_ID.fullmatch(value) else ''


def _selection(raw):
    raw = raw if isinstance(raw, dict) else {}
    background = raw.get('background')
    return {'background': background if background in BACKGROUNDS else 'auto',
            'landscape_pack': _pack_id(raw.get('landscape_pack')),
            'scene_customization': _customization(raw.get('scene_customization'))}


def normalize_living_config(config):
    """Preserve full user configuration, normalizing only presentation fields."""
    cfg = copy.deepcopy(config) if isinstance(config, dict) else {}
    cfg.update(_selection(cfg))
    for key, default in (('persistent_weather', True), ('battery_saver', True)):
        cfg[key] = cfg[key] if isinstance(cfg.get(key), bool) else default
    cfg['atmospheric_intensity'] = _number(cfg.get('atmospheric_intensity'), .5, 0., 1.)
    presets = cfg.get('presets')
    cfg['presets'] = {name.strip(): _selection(value) for name, value in list(presets.items())[:MAX_COLLECTION]
                      if isinstance(name, str) and 0 < len(name.strip()) <= 64 and isinstance(value, dict)} if isinstance(presets, dict) else {}
    favorites = cfg.get('favorites')
    unique = []
    for value in favorites[:MAX_COLLECTION] if isinstance(favorites, list) else []:
        if not isinstance(value, dict):
            continue
        item = _selection(value)
        if item not in unique:
            unique.append(item)
    cfg['favorites'] = unique
    schedule = cfg.get('schedule')
    schedule = schedule if isinstance(schedule, dict) else {}
    entries = {}
    raw_entries = schedule.get('entries')
    for row in raw_entries[:MAX_COLLECTION] if isinstance(raw_entries, list) else []:
        if not isinstance(row, dict):
            continue
        minute = row.get('minute')
        if type(minute) is not int or not 0 <= minute < 1440:
            continue
        entries[minute] = {'minute': minute, **_selection(row)}
    interval = schedule.get('rotation_minutes')
    interval = int(_number(interval, 0, 0, 1440))
    interval = max(5, interval) if interval else 0
    cfg['schedule'] = {'enabled': schedule.get('enabled') is True,
                       'entries': [entries[key] for key in sorted(entries)],
                       'rotation_minutes': interval}
    return cfg


def resolve_selection(config, now=None):
    """Select local scheduled art; entries win over optional favorite rotation."""
    cfg = normalize_living_config(config)
    selected = _selection(cfg)
    schedule = cfg['schedule']
    if not schedule['enabled']:
        return selected
    epoch = time.time() if now is None else _number(now, float('nan'), -1e12, 1e12)
    if not math.isfinite(epoch):
        return selected
    try:
        local = datetime.fromtimestamp(epoch)
    except (ValueError, OverflowError, OSError):
        return selected
    minute = local.hour * 60 + local.minute
    if schedule['entries']:
        candidates = [row for row in schedule['entries'] if row['minute'] <= minute]
        return _selection(candidates[-1] if candidates else schedule['entries'][-1])
    if schedule['rotation_minutes'] and cfg['favorites']:
        return copy.deepcopy(cfg['favorites'][(minute // schedule['rotation_minutes']) % len(cfg['favorites'])])
    return selected


def save_preset(config, name):
    if not isinstance(name, str) or not name.strip() or len(name.strip()) > 64:
        raise ValueError('Preset name must contain 1–64 characters')
    cfg = normalize_living_config(config)
    name = name.strip()
    if name not in cfg['presets'] and len(cfg['presets']) >= MAX_COLLECTION:
        raise ValueError('At most 24 presets are supported')
    cfg['presets'][name] = _selection(cfg)
    return cfg


def load_preset(config, name):
    cfg = normalize_living_config(config)
    if not isinstance(name, str) or name not in cfg['presets']:
        raise ValueError('Preset is missing')
    cfg.update(copy.deepcopy(cfg['presets'][name]))
    return cfg


def add_favorite(config, selection=None):
    cfg = normalize_living_config(config)
    selected = _selection(cfg if selection is None else selection)
    if selected not in cfg['favorites']:
        if len(cfg['favorites']) >= MAX_COLLECTION:
            raise ValueError('At most 24 favorites are supported')
        cfg['favorites'].append(selected)
    return cfg


def remove_favorite(config, index):
    cfg = normalize_living_config(config)
    if type(index) is not int or not 0 <= index < len(cfg['favorites']):
        raise ValueError('Favorite is missing')
    cfg['favorites'].pop(index)
    return cfg


def preview_scene(scene, request, now=None):
    """Strict transient presentation metadata; hour 24 is next local midnight."""
    result = copy.deepcopy(scene) if isinstance(scene, dict) else {}
    result['preview'] = False
    now = time.time() if now is None else now
    if not isinstance(request, dict) or request.get('enabled') is not True:
        return result
    hour, stamp, scenario = request.get('hour'), request.get('generatedAt'), request.get('scenario')
    if isinstance(hour, bool) or not isinstance(hour, (int, float)) or not 0 <= hour <= 24:
        return result
    if isinstance(stamp, bool) or not isinstance(stamp, (int, float)):
        return result
    try:
        if not math.isfinite(hour) or not math.isfinite(stamp) or not -300 <= now - stamp / 1000 <= 7200:
            return result
        if scenario not in ('sunrise', 'day', 'night', 'rain', 'snow', 'storm'):
            return result
        local = datetime.fromtimestamp(now).replace(hour=0, minute=0, second=0, microsecond=0) + timedelta(hours=hour)
        result.update(preview=True, previewClock=int(local.timestamp() * 1000), previewScenario=scenario)
    except (ValueError, OverflowError, TypeError, OSError):
        pass
    return result


def pack_store():
    return Path(os.environ.get('XDG_DATA_HOME', Path.home() / '.local/share')).expanduser() / 'dynwall' / 'packs'


def pack_directory(pack_id):
    if not _pack_id(pack_id):
        raise ValueError('Invalid pack id')
    installed = pack_store() / pack_id
    if installed.exists():
        return installed
    return Path(__file__).resolve().parent / 'packs' / pack_id


def _relative_asset(name):
    if not isinstance(name, str) or '\\' in name or '\x00' in name:
        raise ValueError('Invalid foreground path')
    path = PurePosixPath(name)
    if path.is_absolute() or not path.parts or any(part in ('.', '..') for part in path.parts) or path.suffix.lower() != '.png':
        raise ValueError('Foreground must be a relative PNG path inside the pack')
    return path


def _regular(path, maximum):
    try:
        info = path.lstat()
    except OSError as error:
        raise ValueError(f'Missing pack asset: {path.name}') from error
    if not stat.S_ISREG(info.st_mode) or info.st_size > maximum:
        raise ValueError('Pack assets must be bounded regular files, not symlinks')


def load_pack(path):
    """Validate a manifest plus image before returning native-ready metadata."""
    root = Path(path).expanduser()
    if root.is_file():
        if root.name != 'manifest.json':
            raise ValueError('Choose a pack folder, manifest.json, or import an archive')
        root = root.parent
    if root.is_symlink() or not root.is_dir():
        raise ValueError('Pack folder is missing or is a symlink')
    root = root.resolve()
    manifest_path = root / 'manifest.json'
    _regular(manifest_path, MAX_MANIFEST_BYTES)
    try:
        document = json.loads(manifest_path.read_text(encoding='utf-8'))
    except (OSError, UnicodeError, ValueError) as error:
        raise ValueError('Pack manifest is corrupt') from error
    if not isinstance(document, dict) or type(document.get('schemaVersion')) is not int or document['schemaVersion'] != 1:
        raise ValueError('Unsupported landscape pack version')
    pack_id = _pack_id(document.get('id'))
    name = document.get('name')
    horizon = document.get('horizon')
    if not pack_id or not isinstance(name, str) or not name.strip() or len(name) > 100:
        raise ValueError('Pack id or name is invalid')
    if _number(horizon, -1, .1, .95) == -1 or not .1 <= horizon <= .95:
        raise ValueError('Pack horizon must be finite and between 0.1 and 0.95')
    relative = _relative_asset(document.get('foreground'))
    foreground = root.joinpath(*relative.parts)
    current = root
    for part in relative.parts:
        current = current / part
        if current.is_symlink():
            raise ValueError('Foreground symlinks are not allowed')
    _regular(foreground, MAX_ASSET_BYTES)
    try:
        with Image.open(foreground) as image:
            if image.format != 'PNG' or image.width > 8192 or image.height > 8192 or image.width * image.height > MAX_PIXELS:
                raise ValueError('Foreground image exceeds pack limits')
            image.verify()
    except (OSError, SyntaxError, Image.DecompressionBombError) as error:
        raise ValueError('Foreground image is corrupt') from error
    metadata = {key: document[key] for key in ('author', 'license', 'description')
                if isinstance(document.get(key), str) and len(document[key]) <= 1000}
    return {'schemaVersion': 1, 'id': pack_id, 'name': name.strip(), 'horizon': float(horizon),
            'foreground': str(foreground), 'root': str(root), **metadata}


def _foreground(pack):
    with Image.open(pack['foreground']) as source:
        image = source.convert('RGBA')
    # Existing cutout alpha preserves treetops above the horizon. An opaque photo
    # is cut along its marked horizon instead of covering the animated sky.
    if image.getchannel('A').getextrema()[0] == 255:
        alpha = Image.new('L', image.size, 255)
        alpha.paste(0, (0, 0, image.width, round(image.height * pack['horizon'])))
        image.putalpha(alpha)
    return image


def _write_private(path, data):
    with path.open('xb') as handle:
        os.chmod(path, 0o600)
        handle.write(data)
        handle.flush()
        os.fsync(handle.fileno())


def _extract_archive(source, temporary):
    if source.stat().st_size > MAX_ASSET_BYTES + MAX_MANIFEST_BYTES:
        raise ValueError('Pack archive is too large')
    try:
        with zipfile.ZipFile(source) as archive:
            entries = archive.infolist()
            if len(entries) > 8 or sum(item.file_size for item in entries) > MAX_ASSET_BYTES + MAX_MANIFEST_BYTES:
                raise ValueError('Pack archive exceeds asset limits')
            seen = set()
            for item in entries:
                name = PurePosixPath(item.filename)
                mode = item.external_attr >> 16
                if name.is_absolute() or not name.parts or any(part in ('.','..') for part in name.parts) or '\\' in item.filename or '\x00' in item.filename or stat.S_ISLNK(mode) or item.filename in seen:
                    raise ValueError('Unsafe pack archive path')
                seen.add(item.filename)
                if item.is_dir():
                    continue
                if name.suffix.lower() not in ('.json', '.png'):
                    raise ValueError('Landscape packs may contain only JSON and PNG assets')
                target = temporary.joinpath(*name.parts)
                target.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
                _write_private(target, archive.read(item))
    except (zipfile.BadZipFile, RuntimeError) as error:
        raise ValueError('Landscape pack archive is corrupt') from error
    manifests = list(temporary.glob('manifest.json')) + list(temporary.glob('*/manifest.json'))
    if len(manifests) != 1:
        raise ValueError('Archive must contain exactly one pack manifest')
    return manifests[0].parent


def import_pack(source, destination=None):
    """Import into a collection directory; existing ids are never overwritten."""
    source = Path(source).expanduser()
    store = pack_store() if destination is None else Path(destination).expanduser()
    if source.is_symlink():
        raise ValueError('Pack source may not be a symlink')
    if source.is_file() and source.name != 'manifest.json':
        with tempfile.TemporaryDirectory(prefix='dynwall-pack-') as td:
            extracted = _extract_archive(source, Path(td))
            return import_pack(extracted, store)
    pack = load_pack(source)
    store.mkdir(mode=0o700, parents=True, exist_ok=True)
    target = store / pack['id']
    if target.exists() or target.is_symlink():
        raise FileExistsError(f'Landscape pack {pack["id"]} is already installed')
    staging = Path(tempfile.mkdtemp(prefix='.pack-', dir=store))
    try:
        image = _foreground(pack)
        asset = staging / 'foreground.png'
        with asset.open('xb') as handle:
            os.chmod(asset, 0o600)
            image.save(handle, format='PNG')
            handle.flush(); os.fsync(handle.fileno())
        manifest = {key: pack[key] for key in ('schemaVersion','id','name','horizon','author','license','description') if key in pack}
        manifest['foreground'] = 'foreground.png'
        _write_private(staging / 'manifest.json', (json.dumps(manifest, ensure_ascii=False, indent=2)+'\n').encode())
        load_pack(staging)
        os.rename(staging, target)
    finally:
        if staging.exists():
            shutil.rmtree(staging)
    return load_pack(target)


def export_pack(pack, destination):
    """Atomically export a validated pack archive with owner-only permissions."""
    pack = load_pack(pack['root'] if isinstance(pack, dict) else pack)
    destination = Path(destination).expanduser()
    destination.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
    fd, name = tempfile.mkstemp(prefix='.pack-export-', dir=destination.parent)
    os.close(fd)
    temporary = Path(name)
    try:
        with zipfile.ZipFile(temporary, 'w', compression=zipfile.ZIP_DEFLATED) as archive:
            manifest = {key: pack[key] for key in ('schemaVersion','id','name','horizon','author','license','description') if key in pack}
            manifest['foreground'] = 'foreground.png'
            archive.writestr('manifest.json', json.dumps(manifest, ensure_ascii=False, indent=2)+'\n')
            archive.write(pack['foreground'], 'foreground.png')
        with temporary.open('rb') as handle:
            os.fsync(handle.fileno())
        os.replace(temporary, destination)
    finally:
        temporary.unlink(missing_ok=True)
    return destination


def list_packs():
    packs = {}
    for collection in (Path(__file__).resolve().parent / 'packs', pack_store()):
        if not collection.is_dir():
            continue
        for path in sorted(collection.iterdir()):
            try:
                pack = load_pack(path)
                packs[pack['id']] = pack
            except (ValueError, OSError):
                continue
    return list(packs.values())[:64]


def composite_pack(image, pack, customization=None):
    """Composite foreground with the same horizon/scale contract as native actors."""
    pack = load_pack(pack['root'] if isinstance(pack, dict) else pack)
    c = _customization(customization)
    foreground = _foreground(pack)
    size = (image.width, max(1, round(image.height*c['terrain_scale'])))
    foreground = foreground.resize(size, Image.Resampling.LANCZOS)
    warmth, darkness = c['warmth'], c['darkness']
    if warmth or darkness:
        channels = foreground.split()
        rgb = []
        for index, channel in enumerate(channels[:3]):
            offset = warmth * (18 if index == 0 else -18 if index == 2 else 0)
            rgb.append(channel.point(lambda value, off=offset: round(max(0,min(255,value*(1-darkness*.65)+off)))))
        foreground = Image.merge('RGBA', (*rgb, channels[3]))
    shift = pack['horizon'] + c['horizon'] - .8 - pack['horizon']*c['terrain_scale']
    result = image.convert('RGBA')
    result.alpha_composite(foreground, (0, round(image.height*shift)))
    return result.convert(image.mode if image.mode in ('RGB','RGBA') else 'RGB')
