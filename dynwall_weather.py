#!/usr/bin/env python3
"""Pure helpers for consuming TopWeather data and publishing Dynwall scenes.

The optional ``now`` arguments use epoch seconds, like :func:`time.time`.
Snapshot and scene timestamps remain epoch milliseconds on disk.
"""

from __future__ import annotations

import copy
import json
import math
import os
import tempfile
import time
from collections.abc import Mapping
from pathlib import Path
from typing import Any


SCHEMA_VERSION = 1
MAX_SNAPSHOT_AGE_SECONDS = 2 * 60 * 60
MAX_FUTURE_SKEW_SECONDS = 5 * 60
DEFAULT_FPS = 30
MIN_FPS = 15
MAX_FPS = 60
DEFAULT_QUALITY = "balanced"
QUALITY_LEVELS = frozenset(("low", "balanced", "high"))

_CANONICAL_CURRENT_FIELDS = (
    "cloudCover",
    "precipitation",
    "rain",
    "snowfall",
    "windSpeedKmh",
    "windDirection",
    "weatherCode",
)


def _now_seconds(now: float | None) -> float:
    value = time.time() if now is None else now
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ValueError("now must be finite epoch seconds")
    value = float(value)
    if not math.isfinite(value):
        raise ValueError("now must be finite epoch seconds")
    return value


def _finite_number(value: Any) -> bool:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return False
    try:
        return math.isfinite(value)
    except OverflowError:
        return False


def _json_numbers_are_finite(value: Any) -> bool:
    if isinstance(value, (int, float)) and not isinstance(value, bool):
        return _finite_number(value)
    if isinstance(value, Mapping):
        return all(
            isinstance(key, str) and _json_numbers_are_finite(item)
            for key, item in value.items()
        )
    if isinstance(value, (list, tuple)):
        return all(_json_numbers_are_finite(item) for item in value)
    return True


def _optional_number(
    container: Mapping[str, Any],
    field: str,
    *,
    minimum: float | None = None,
    maximum: float | None = None,
) -> bool:
    value = container.get(field)
    if value is None:
        return True
    if not _finite_number(value):
        return False
    if minimum is not None and value < minimum:
        return False
    if maximum is not None and value > maximum:
        return False
    return True


def _normalise_snapshot(snapshot: Any, now_seconds: float) -> dict[str, Any] | None:
    if not isinstance(snapshot, Mapping) or not _json_numbers_are_finite(snapshot):
        return None
    schema_version = snapshot.get("schemaVersion")
    if not isinstance(schema_version, int) or isinstance(schema_version, bool):
        return None
    if schema_version != SCHEMA_VERSION:
        return None

    fetched_at = snapshot.get("fetchedAt")
    if isinstance(fetched_at, bool) or not isinstance(fetched_at, int):
        return None
    fetched_seconds = fetched_at / 1000
    if now_seconds - fetched_seconds > MAX_SNAPSHOT_AGE_SECONDS:
        return None
    if fetched_seconds - now_seconds > MAX_FUTURE_SKEW_SECONDS:
        return None

    provider = snapshot.get("provider")
    location = snapshot.get("location")
    unit = snapshot.get("unit")
    current = snapshot.get("current")
    if not isinstance(provider, str) or not provider.strip():
        return None
    if not isinstance(location, str):
        return None
    if unit not in ("c", "f"):
        return None
    if not isinstance(current, Mapping):
        return None

    if not _optional_number(snapshot, "latitude", minimum=-90, maximum=90):
        return None
    if not _optional_number(snapshot, "longitude", minimum=-180, maximum=180):
        return None

    number_rules = {
        "cloudCover": (0, 100),
        "precipitation": (0, None),
        "rain": (0, None),
        "snowfall": (0, None),
        "windSpeedKmh": (0, None),
        "windDirection": (0, 360),
        "temp": (None, None),
        "feelsLike": (None, None),
        "humidity": (0, 100),
        "windSpeed": (0, None),
    }
    for field, (minimum, maximum) in number_rules.items():
        if not _optional_number(current, field, minimum=minimum, maximum=maximum):
            return None

    weather_code = current.get("weatherCode")
    if weather_code is not None:
        if isinstance(weather_code, bool) or not isinstance(weather_code, (str, int, float)):
            return None
        if isinstance(weather_code, str) and not weather_code.strip():
            return None
        if isinstance(weather_code, (int, float)) and not _finite_number(weather_code):
            return None

    if "isNight" in current and current["isNight"] is not None and not isinstance(
        current["isNight"], bool
    ):
        return None
    for field in ("desc", "glyph", "sunrise", "sunset", "moonPhase"):
        if field in current and current[field] is not None and not isinstance(current[field], str):
            return None

    normalised = copy.deepcopy(dict(snapshot))
    normalised.setdefault("latitude", None)
    normalised.setdefault("longitude", None)
    normalised_current = copy.deepcopy(dict(current))
    for field in _CANONICAL_CURRENT_FIELDS:
        normalised_current.setdefault(field, None)
    normalised["current"] = normalised_current
    return normalised


def _default_weather_path() -> Path:
    cache_home = os.environ.get("XDG_CACHE_HOME")
    if cache_home:
        return Path(cache_home).expanduser() / "topweather" / "current.json"
    return Path.home() / ".cache" / "topweather" / "current.json"


def load_weather(path: os.PathLike[str] | str | None = None, now: float | None = None):
    """Load a fresh schema-v1 TopWeather snapshot, or return ``None``.

    Reading the local cache never performs network or desktop operations.
    ``now`` is epoch seconds and exists to make freshness checks deterministic.
    """

    try:
        now_seconds = _now_seconds(now)
        source = _default_weather_path() if path is None else Path(path).expanduser()
        with source.open("r", encoding="utf-8") as handle:
            snapshot = json.load(handle)
        return _normalise_snapshot(snapshot, now_seconds)
    except (OSError, UnicodeError, json.JSONDecodeError, TypeError, ValueError):
        return None


def _display_number(value: Any) -> str:
    if not _finite_number(value):
        return ""
    return format(value, ".12g")


def weather_description(snapshot: Mapping[str, Any] | None) -> str:
    """Return concise prompt context using only measurements that are present."""

    if not isinstance(snapshot, Mapping) or not isinstance(snapshot.get("current"), Mapping):
        return "Weather data unavailable"

    current = snapshot["current"]
    conditions: list[str] = []
    desc = current.get("desc")
    if isinstance(desc, str) and desc.strip():
        conditions.append(desc.strip())

    temp = _display_number(current.get("temp"))
    unit = snapshot.get("unit")
    if temp and unit in ("c", "f"):
        conditions.append(f"{temp}°{unit.upper()}")

    cloud_cover = _display_number(current.get("cloudCover"))
    if cloud_cover:
        conditions.append(f"{cloud_cover}% cloud cover")

    precipitation = _display_number(current.get("precipitation"))
    rain = _display_number(current.get("rain"))
    snowfall = _display_number(current.get("snowfall"))
    if precipitation:
        conditions.append(f"{precipitation} mm/h precipitation")
    else:
        if rain:
            conditions.append(f"{rain} mm/h rain")
        if snowfall:
            conditions.append(f"{snowfall} mm/h snowfall water equivalent")

    wind_speed = _display_number(current.get("windSpeedKmh"))
    wind_direction = _display_number(current.get("windDirection"))
    if wind_speed:
        wind = f"{wind_speed} km/h wind"
        if wind_direction:
            wind += f" from {wind_direction}°"
        conditions.append(wind)

    location = snapshot.get("location")
    provider = snapshot.get("provider")
    prefix = "Observed weather"
    if isinstance(location, str) and location.strip():
        prefix += f" for {location.strip()}"
    if not conditions:
        conditions.append("measurements unavailable")
    result = f"{prefix}: " + "; ".join(conditions)
    if isinstance(provider, str) and provider.strip():
        result += f" (source: {provider.strip()})"
    return result


def _renderer_config(cfg: Mapping[str, Any] | None) -> dict[str, Any]:
    cfg = cfg if isinstance(cfg, Mapping) else {}

    enabled_value = cfg.get("allow_animation", True)
    enabled = enabled_value if isinstance(enabled_value, bool) else True

    fps_value = cfg.get("weather_fps", DEFAULT_FPS)
    if not _finite_number(fps_value):
        fps = DEFAULT_FPS
    else:
        fps = int(fps_value)
        fps = max(MIN_FPS, min(MAX_FPS, fps))

    quality_value = cfg.get("weather_quality", DEFAULT_QUALITY)
    quality = quality_value.lower() if isinstance(quality_value, str) else DEFAULT_QUALITY
    if quality not in QUALITY_LEVELS:
        quality = DEFAULT_QUALITY

    seasonal_value = cfg.get("seasonal_effects", True)
    seasonal = seasonal_value if isinstance(seasonal_value, bool) else True
    return {"enabled": enabled, "fps": fps, "quality": quality, "seasonalEffects": seasonal}


def build_scene_document(
    spec: Any,
    snapshot: Any,
    cfg: Mapping[str, Any] | None,
    now: float | None = None,
) -> dict[str, Any]:
    """Build a schema-v1 scene document without performing I/O."""

    now_seconds = _now_seconds(now)
    scene_spec = copy.deepcopy(spec)
    if (
        isinstance(cfg, Mapping)
        and cfg.get("mesh_enabled") is False
        and isinstance(scene_spec, dict)
    ):
        mesh = scene_spec.get("mesh")
        scene_spec["mesh"] = copy.deepcopy(dict(mesh)) if isinstance(mesh, Mapping) else {}
        scene_spec["mesh"]["style"] = "none"
    if isinstance(cfg, Mapping) and cfg.get("landscape_enabled") is False and isinstance(scene_spec, dict):
        landscape = scene_spec.get("landscape")
        scene_spec["landscape"] = copy.deepcopy(dict(landscape)) if isinstance(landscape, Mapping) else {}
        scene_spec["landscape"]["style"] = "none"
    from dynwall_living import normalize_living_config
    living = normalize_living_config(dict(cfg) if isinstance(cfg, Mapping) else {})
    # Publish only presentation fields, never provider credentials or arbitrary config.
    living = {key: living[key] for key in ("background", "landscape_pack", "scene_customization",
        "presets", "favorites", "schedule", "persistent_weather", "atmospheric_intensity", "battery_saver") if key in living}
    living["landscape_enabled"] = not isinstance(cfg, Mapping) or cfg.get("landscape_enabled") is not False
    return {
        "living": living,
        "schemaVersion": SCHEMA_VERSION,
        "generatedAt": int(now_seconds * 1000),
        "spec": scene_spec,
        "weather": _normalise_snapshot(snapshot, now_seconds),
        "renderer": _renderer_config(cfg),
    }


def write_scene(path: os.PathLike[str] | str, document: Mapping[str, Any]) -> None:
    """Atomically write a JSON scene file with mode ``0600``."""

    destination = Path(path).expanduser()
    destination.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
    temporary_path: str | None = None
    try:
        with tempfile.NamedTemporaryFile(
            mode="w",
            encoding="utf-8",
            dir=destination.parent,
            prefix=f".{destination.name}.",
            suffix=".tmp",
            delete=False,
        ) as handle:
            temporary_path = handle.name
            json.dump(document, handle, ensure_ascii=False, separators=(",", ":"), allow_nan=False)
            handle.write("\n")
            handle.flush()
            os.fsync(handle.fileno())
        os.chmod(temporary_path, 0o600)
        os.replace(temporary_path, destination)
        temporary_path = None
        os.chmod(destination, 0o600)
    finally:
        if temporary_path is not None:
            try:
                os.unlink(temporary_path)
            except FileNotFoundError:
                pass
