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


def _base_image(source: Path, size: tuple[int, int], now: datetime) -> Image.Image:
    with Image.open(source) as image:
        base = ImageOps.fit(image.convert("RGB"), size, Image.Resampling.LANCZOS,
                            centering=(0.5, 0.48))
    hour = now.hour + now.minute / 60
    # Preserve texture and retain warm cabin details through nighttime.
    if hour < 5 or hour >= 21:
        factor = 0.40
    elif hour < 7:
        factor = 0.40 + (hour - 5) * 0.23
    elif hour < 18:
        factor = 0.95
    else:
        factor = 0.95 - min(3, hour - 18) * 0.18
    if factor != 1:
        base = ImageEnhance.Brightness(base).enhance(factor)
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
    base = _base_image(source, size, now)
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
