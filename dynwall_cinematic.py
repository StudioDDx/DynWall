"""Cinematic still-based animation for service-owned full-scene landscape packs.

Used only for the opt-in smokies-cinematic pack. No GNOME Shell extension,
network access, shader execution or per-frame desktop mutations.
"""
from __future__ import annotations

from datetime import datetime
from pathlib import Path
import math
import random

from PIL import Image, ImageChops, ImageDraw, ImageEnhance, ImageFilter, ImageOps


def _sun_altitude(now: datetime, weather: dict | None) -> float | None:
    """Approximate solar elevation from observed location and local time.

    No sunrise/sunset clock-hour assumptions: UTC offset, longitude, latitude
    and day of year determine the lighting envelope.
    """
    weather = weather if isinstance(weather, dict) else {}
    lat, lon = weather.get("latitude"), weather.get("longitude")
    if any(type(v) not in (int, float) or not math.isfinite(v)
           for v in (lat, lon)) or not (-90 <= lat <= 90 and -180 <= lon <= 180):
        return None
    from datetime import timezone
    local = now.astimezone() if now.tzinfo is None else now
    utc = local.astimezone(timezone.utc)
    day = utc.timetuple().tm_yday
    h = utc.hour + utc.minute / 60 + utc.second / 3600
    gamma = 2 * math.pi / 365 * (day - 1 + (h - 12) / 24)
    eqtime = 229.18 * (0.000075 + 0.001868 * math.cos(gamma)
                       - 0.032077 * math.sin(gamma) - 0.014615 * math.cos(2*gamma)
                       - 0.040849 * math.sin(2*gamma))
    decl = (0.006918 - 0.399912 * math.cos(gamma) + 0.070257 * math.sin(gamma)
            - 0.006758 * math.cos(2*gamma) + 0.000907 * math.sin(2*gamma)
            - 0.002697 * math.cos(3*gamma) + 0.00148 * math.sin(3*gamma))
    minutes = h * 60 + eqtime + 4 * lon
    hour_angle = math.radians((minutes % 1440) / 4 - 180)
    latitude = math.radians(lat)
    cosine = math.sin(latitude) * math.sin(decl) + math.cos(latitude) * math.cos(decl) * math.cos(hour_angle)
    return math.degrees(math.asin(max(-1, min(1, cosine))))


def _base_image(source: Path, size: tuple[int, int], now: datetime,
                weather: dict | None = None) -> Image.Image:
    with Image.open(source) as image:
        base = ImageOps.fit(image.convert("RGB"), size, Image.Resampling.LANCZOS,
                            centering=(0.5, 0.48))
    weather = weather if isinstance(weather, dict) else {}
    current = weather.get("current", {})
    current = current if isinstance(current, dict) else {}
    altitude = _sun_altitude(now, weather)
    # Fixed-phase fallback is used only when TopWeather has no coordinates.
    if altitude is None:
        hour = now.hour + now.minute / 60
        if 7 <= hour < 18:
            altitude = 35.0
        elif 6 <= hour < 7 or 18 <= hour < 19:
            altitude = -2.0
        else:
            altitude = -25.0
    daylight = max(0.0, min(1.0, (altitude + 9) / 35))
    cloud_cover = current.get("cloudCover")
    clouds = cloud_cover / 100 if type(cloud_cover) in (int, float) and math.isfinite(cloud_cover) and 0 <= cloud_cover <= 100 else 0
    daylight *= 1 - 0.28 * clouds
    dusk = max(0.0, 1 - abs(altitude - 1.0) / 17.0)
    # The source painting has a fixed sunset position. These color grades
    # change the ambience, NOT sun placement, shadow geometry or season.
    brightness = 0.24 + 0.76 * daylight
    base = ImageEnhance.Brightness(base).enhance(brightness)
    if daylight < 0.55:
        night = 1 - daylight / 0.55
        overlay = Image.new("RGB", size, (30, 53, 98))
        base = Image.blend(base, overlay, 0.28 * night)
    elif dusk > 0:
        amber = Image.new("RGB", size, (192, 104, 69))
        base = Image.blend(base, amber, 0.065 * dusk)
    return base


def _fog_texture(size: tuple[int, int]) -> Image.Image:
    """Soft translucent texture; wraparound offset gives seamless loop motion."""
    width, height = size
    small = (max(64, width // 10), max(32, height // 10))
    rng = random.Random(35172)
    canvas = Image.new("L", small, 0)
    brush = ImageDraw.Draw(canvas)
    for _ in range(135):
        x = rng.randrange(small[0])
        y = rng.randrange(round(small[1] * .36), round(small[1] * .75))
        rx = rng.randrange(max(4, small[0] // 60), max(5, small[0] // 10))
        ry = rng.randrange(2, max(4, small[1] // 22))
        alpha = rng.randrange(18, 58)
        # Tile horizontally so rolls do not expose a seam.
        for shift in (-small[0], 0, small[0]):
            brush.ellipse((x+shift-rx, y-ry, x+shift+rx, y+ry), fill=alpha)
    canvas = canvas.filter(ImageFilter.GaussianBlur(max(2, small[1] / 70)))
    return canvas.resize(size, Image.Resampling.BILINEAR)


def build_frames(source: Path, target: Path, size: tuple[int, int], count: int,
                 clock: datetime | None = None, weather: dict | None = None) -> list[Path]:
    """Write independent fully-rendered frames into an empty generation directory."""
    if not 1 <= count <= 120:
        raise ValueError("frame count out of range")
    if min(size) < 1 or max(size) > 15360:
        raise ValueError("invalid canvas size")
    now = clock or datetime.now()
    base = _base_image(source, size, now, weather)
    fog = _fog_texture(size)
    weather = weather if isinstance(weather, dict) else {}
    current = weather.get("current", {})
    current = current if isinstance(current, dict) else {}
    cloud_cover = current.get("cloudCover")
    cloud_cover = cloud_cover if type(cloud_cover) in (int, float) and math.isfinite(cloud_cover) else 50
    strength = max(0.4, min(1.5, 0.55 + cloud_cover / 135))
    # Very subtle loop-safe valley haze rather than independent overlaid scenery.
    result = []
    target.mkdir(parents=True, exist_ok=False)
    for index in range(count):
        phase = index / count
        offset = round(size[0] * 0.08 * math.sin(phase * math.tau))
        opacity = 0.88 + 0.12 * math.cos(phase * math.tau)
        alpha = ImageChops.offset(fog, offset, 0).point(
            lambda v, k=strength * opacity: min(100, round(v * k)))
        veil = Image.new("RGBA", size, (185, 195, 204, 0))
        veil.putalpha(alpha)
        frame = Image.alpha_composite(base.convert("RGBA"), veil).convert("RGB")
        filename = target / f"f{index:03d}.png"
        frame.save(filename, "PNG", optimize=False)
        result.append(filename)
    return result
