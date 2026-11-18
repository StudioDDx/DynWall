#!/usr/bin/python3
"""Reproducibly author the original Woodland River foreground, without downloads.

Tree and shrub art comes from painted RGBA sprites in packs/woodland-src/ when
available; any missing sprite falls back to the original procedural drawing so
the pack always rebuilds. Sprites get aerial-perspective haze blended per depth
layer so they sit inside the painted ridge palette instead of pasted on top.
"""
import json
import math
from pathlib import Path
import random
from PIL import Image, ImageDraw

ROOT = Path(__file__).resolve().parent / 'woodland'
SRC = Path(__file__).resolve().parent / 'woodland-src'
W, H = 2560, 1440
rng = random.Random(572004)
image = Image.new('RGBA', (W, H))
draw = ImageDraw.Draw(image)

SPRITE_NAMES = ('pine-tall', 'pine-medium', 'pine-young', 'oak-full',
                'treeline-band', 'rhododendron', 'grass-clump')


def load_sprites():
    sprites = {}
    for name in SPRITE_NAMES:
        path = SRC / f'{name}.png'
        if not path.is_file():
            continue
        try:
            with Image.open(path) as sprite:
                sprites[name] = sprite.convert('RGBA').copy()
        except (OSError, ValueError):
            continue
    return sprites


sprites = load_sprites()


def haze(sprite, color, fraction):
    """Blend a sprite toward the layer's air color; keep the original alpha."""
    if fraction <= 0:
        return sprite
    rgb = sprite.convert('RGB')
    solid = Image.new('RGB', rgb.size, color)
    blended = Image.blend(rgb, solid, fraction)
    result = blended.convert('RGBA')
    result.putalpha(sprite.getchannel('A'))
    return result


def paste_sprite(canvas, name, cx, base_y, height, fraction, color, flip=False):
    sprite = sprites.get(name)
    if sprite is None:
        return False
    scale = height / sprite.height
    size = (max(1, round(sprite.width * scale)), max(1, round(height)))
    cut = sprite.resize(size, Image.Resampling.LANCZOS)
    if flip:
        cut = cut.transpose(Image.Transpose.FLIP_LEFT_RIGHT)
    canvas.alpha_composite(haze(cut, color, fraction),
                           (round(cx - size[0] / 2), round(base_y - size[1])))
    return True


def ridge_y(x, base, amplitude, phase):
    return H * (base + math.sin(x / W * 8 + phase) * amplitude
                + math.sin(x / W * 18 + phase) * amplitude * 0.23)


def ridge(base, amplitude, phase, fill):
    points = [(x, round(ridge_y(x, base, amplitude, phase)))
              for x in range(-10, W + 11, 8)]
    draw.polygon(points + [(W + 10, H + 10), (-10, H + 10)], fill=fill)


# Low layered contours representing Smoky Mountain ridges; all sky is transparent.
ridge(0.724, 0.027, 0.4, (115, 145, 141, 255))
ridge(0.771, 0.022, 2.9, (86, 119, 112, 255))

# Distant woodland following the far mountain contour (fallback; the painted
# treeline band below replaces this when present).
for x in range(15, W, 21):
    y = H * (0.754 + math.sin(x / W * 8 + 0.7) * 0.018)
    height = rng.uniform(17, 45)
    draw.line((x, y, x, y - height), fill=(71, 107, 103, 255), width=2)
    draw.polygon([(x, y - height), (x - height * 0.30, y - 6), (x + height * 0.30, y - 6)], fill=(80, 115, 109, 255))

ridge(0.82, 0.032, 0.5, (66, 105, 87, 255))

# Continuous distant conifer canopy hugging the third ridge crest.
FAR_AIR = (86, 119, 112)
MID_AIR = (66, 105, 87)
NEAR_AIR = (47, 83, 69)
if 'treeline-band' in sprites:
    band_h = 132
    tile_w = 300
    band = sprites['treeline-band'].resize((tile_w, band_h), Image.Resampling.LANCZOS)
    x = -40
    flip = False
    while x < W:
        cx = x + tile_w / 2
        top = ridge_y(cx, 0.82, 0.032, 0.5) - band_h + 14
        tile = band.transpose(Image.Transpose.FLIP_LEFT_RIGHT) if flip else band
        image.alpha_composite(haze(tile, FAR_AIR, 0.42), (x, round(top)))
        x += round(tile_w * 0.72)
        flip = not flip

# Sparse far trees on the second ridge, well behind the canopy band.
for cx, base_y, height, flip in [
    (180, 1108, 88, False), (360, 1100, 74, True), (560, 1112, 96, False),
    (760, 1098, 70, True), (2050, 1104, 84, False), (2250, 1112, 66, True),
    (2430, 1100, 92, False),
]:
    paste_sprite(image, 'pine-young', cx, base_y, height, 0.55, FAR_AIR, flip)

ridge(0.895, 0.045, 3.0, (47, 83, 69, 255))

# Mid-ground spruces on the third ridge fill, in front of the canopy band.
for cx, base_y, height, flip in [
    (830, 1198, 120, False), (1010, 1206, 100, True), (1200, 1194, 132, False),
    (1880, 1200, 118, True), (2060, 1208, 96, False), (2320, 1196, 126, False),
    (2500, 1204, 104, True),
]:
    paste_sprite(image, 'pine-medium', cx, base_y, height, 0.30, MID_AIR, flip)

# Open mountain river threading through the valley; outlined banks remain gentle and flat.
river = [
    (1553, 1102), (1510, 1120), (1380, 1147), (1350, 1165), (1460, 1190),
    (1535, 1224), (1485, 1260), (1270, 1321), (1130, 1440), (1755, 1440),
    (1705, 1337), (1624, 1281), (1692, 1232), (1620, 1192), (1482, 1159),
    (1470, 1148), (1560, 1111)
]
draw.polygon(river, fill=(92, 133, 139, 255))
draw.line(river[:10], fill=(148, 161, 132, 255), width=5)

water = Image.new('RGBA', (W, H))
water_draw = ImageDraw.Draw(water)
for y in range(1160, H, 13):
    left = 1370 + math.sin(y * 0.023) * 120
    width = 55 + (y - 1160) * 0.42
    water_draw.line((left, y, left + width, y), fill=(123, 155, 154, 180), width=2)

water_mask = Image.new('L', (W, H))
ImageDraw.Draw(water_mask).polygon(river, fill=255)
water.putalpha(Image.composite(water.getchannel('A'), Image.new('L', (W, H)), water_mask))
image.alpha_composite(water)

# Rustic Wooden Footbridge over the upper river bend.
bridge_y = 1152
draw.polygon([(1465, bridge_y - 4), (1545, bridge_y - 8), (1552, bridge_y + 8), (1472, bridge_y + 12)], fill=(75, 62, 48, 255))
draw.line((1465, bridge_y - 4, 1545, bridge_y - 8), fill=(110, 92, 72, 255), width=3)
draw.line((1472, bridge_y + 12, 1552, bridge_y + 8), fill=(110, 92, 72, 255), width=3)
# Railing posts
for bx in range(1470, 1550, 15):
    by = bridge_y - 6 + (bx - 1470) * -0.05
    draw.line((bx, by, bx, by - 12), fill=(60, 48, 36, 255), width=2)
draw.line((1470, bridge_y - 18, 1548, bridge_y - 21), fill=(95, 78, 60, 255), width=2)

# Rustic Appalachian Log Cabin (Smokies classic!).
cabin_x, cabin_y = 860, 1225
cw, ch = 110, 65
# Log wall base
draw.rectangle([(cabin_x, cabin_y), (cabin_x + cw, cabin_y + ch)], fill=(72, 56, 42, 255))
# Horizontal log lines
for ly in range(cabin_y + 6, cabin_y + ch, 8):
    draw.line((cabin_x, ly, cabin_x + cw, ly), fill=(48, 36, 26, 255), width=1)
# Gabled shingle roof
roof_pts = [(cabin_x - 12, cabin_y + 2), (cabin_x + cw / 2, cabin_y - 32), (cabin_x + cw + 12, cabin_y + 2)]
draw.polygon(roof_pts, fill=(54, 46, 38, 255))
draw.polygon([(cabin_x, cabin_y), (cabin_x + cw / 2, cabin_y - 28), (cabin_x + cw, cabin_y)], fill=(65, 52, 40, 255))
# Stone chimney
draw.rectangle([(cabin_x + cw - 18, cabin_y - 38), (cabin_x + cw - 4, cabin_y + ch - 10)], fill=(92, 90, 85, 255))
for cy in range(cabin_y - 34, cabin_y + ch - 10, 6):
    draw.line((cabin_x + cw - 18, cy, cabin_x + cw - 4, cy), fill=(65, 63, 60, 255), width=1)
# Wispy chimney smoke curls
for i in range(12):
    smk_y = cabin_y - 42 - i * 5
    smk_x = cabin_x + cw - 11 + math.sin(i * 0.5) * (4 + i * 0.8)
    alpha = max(10, 110 - i * 8)
    rad = 3 + i * 0.7
    draw.ellipse((smk_x - rad, smk_y - rad, smk_x + rad, smk_y + rad), fill=(215, 220, 225, int(alpha)))
# Cozy illuminated cabin window
draw.rectangle([(cabin_x + 20, cabin_y + 18), (cabin_x + 42, cabin_y + 38)], fill=(255, 210, 110, 240))
draw.line((cabin_x + 31, cabin_y + 18, cabin_x + 31, cabin_y + 38), fill=(80, 60, 40, 255), width=1)
draw.line((cabin_x + 20, cabin_y + 28, cabin_x + 42, cabin_y + 28), fill=(80, 60, 40, 255), width=1)
# Cabin door
draw.rectangle([(cabin_x + 58, cabin_y + 22), (cabin_x + 78, cabin_y + ch)], fill=(45, 32, 22, 255))
# Front porch overhang & posts
draw.rectangle([(cabin_x + 12, cabin_y + ch - 22), (cabin_x + 82, cabin_y + ch - 18)], fill=(85, 68, 52, 255))
draw.line((cabin_x + 15, cabin_y + ch - 18, cabin_x + 15, cabin_y + ch), fill=(55, 42, 30, 255), width=2)
draw.line((cabin_x + 79, cabin_y + ch - 18, cabin_x + 79, cabin_y + ch), fill=(55, 42, 30, 255), width=2)
# Neat firewood stack beside cabin
for wx in range(cabin_x - 22, cabin_x - 4, 5):
    for wy in range(cabin_y + ch - 16, cabin_y + ch, 5):
        draw.ellipse((wx, wy, wx + 4, wy + 4), fill=(110, 85, 58, 255))

# Cades Cove split-rail worm fence.
fence_pts = [(680, 1295), (740, 1285), (790, 1298), (840, 1288), (980, 1295), (1050, 1282), (1120, 1290)]
for idx in range(len(fence_pts) - 1):
    x1, y1 = fence_pts[idx]
    x2, y2 = fence_pts[idx + 1]
    # Vertical interlocking posts
    draw.line((x1, y1 + 10, x1, y1 - 18), fill=(68, 55, 42, 255), width=3)
    draw.line((x1 + 4, y1 + 12, x1 + 4, y1 - 16), fill=(58, 45, 34, 255), width=3)
    # Split rails
    draw.line((x1, y1 - 14, x2, y2 - 14), fill=(88, 72, 56, 255), width=2)
    draw.line((x1, y1 - 5, x2, y2 - 5), fill=(80, 65, 50, 255), width=2)
    draw.line((x1, y1 + 4, x2, y2 + 4), fill=(72, 58, 44, 255), width=2)

# Appalachian Trail Signpost (Smokies Easter Egg!).
sign_x, sign_y = 1170, 1275
draw.line((sign_x, sign_y + 20, sign_x, sign_y - 25), fill=(60, 48, 36, 255), width=3)
draw.polygon([(sign_x - 18, sign_y - 25), (sign_x + 22, sign_y - 25), (sign_x + 26, sign_y - 15), (sign_x - 18, sign_y - 15)], fill=(115, 95, 72, 255))
# White AT marker patch
draw.rectangle([(sign_x - 12, sign_y - 23), (sign_x - 2, sign_y - 17)], fill=(240, 240, 235, 255))

# Black Bear & Cub strolling near the forest edge (Iconic Smokies Easter Egg!).
# Mama Bear
bx, by = 1260, 1252
draw.ellipse((bx - 14, by - 10, bx + 14, by + 8), fill=(28, 24, 22, 255))  # Body
draw.ellipse((bx - 20, by - 12, bx - 10, by - 2), fill=(28, 24, 22, 255))  # Head
draw.ellipse((bx - 23, by - 9, bx - 18, by - 5), fill=(45, 38, 32, 255))   # Snout
draw.ellipse((bx - 18, by - 15, bx - 14, by - 11), fill=(28, 24, 22, 255)) # Ear
# Legs
for lx in (-10, -4, 4, 10):
    draw.line((bx + lx, by + 4, bx + lx, by + 12), fill=(28, 24, 22, 255), width=3)
# Bear Cub
cx, cy = 1290, 1256
draw.ellipse((cx - 8, cy - 6, cx + 8, cy + 5), fill=(28, 24, 22, 255))
draw.ellipse((cx - 12, cy - 8, cx - 5, cy - 1), fill=(28, 24, 22, 255))
for lx in (-5, -1, 3, 6):
    draw.line((cx + lx, cy + 2, cx + lx, cy + 8), fill=(28, 24, 22, 255), width=2)

# Grazing White-Tailed Deer in the right meadow (Smokies Easter Egg!).
dx, dy = 1840, 1375
draw.ellipse((dx - 16, dy - 12, dx + 14, dy + 6), fill=(105, 78, 54, 255))  # Body
draw.line((dx - 12, dy - 8, dx - 22, dy + 8), fill=(85, 62, 42, 255), width=4)  # Neck down grazing
draw.ellipse((dx - 26, dy + 4, dx - 18, dy + 12), fill=(105, 78, 54, 255))     # Head
draw.ellipse((dx + 12, dy - 10, dx + 17, dy - 2), fill=(235, 235, 230, 255))   # White tail patch
for lx in (-10, -3, 5, 11):
    draw.line((dx + lx, dy + 4, dx + lx + 1, dy + 22), fill=(80, 58, 38, 255), width=2)

# Meadow grasses; ground texture stays procedural beneath the sprite clumps.
for _ in range(520):
    x = rng.randrange(W)
    y = rng.randrange(1230, H)
    if 1130 < x < 1760 and y > 1300:
        continue
    length = rng.randrange(5, 28)
    color = rng.choice([(91, 119, 78, 200), (105, 125, 81, 200), (57, 95, 74, 230), (135, 137, 87, 180)])
    draw.line((x, y, x + length * 0.22, y - length), fill=color, width=2)
    if rng.random() < 0.12:
        draw.ellipse((x - 2, y - length - 3, x + 2, y - length + 2), fill=(171, 157, 104, 220))

# Mountain Laurel / Rhododendron along the river and meadow.
RHODO_SPOTS = [
    (780, 1260), (830, 1250), (990, 1265), (1080, 1255),
    (1340, 1210), (1420, 1225), (1600, 1180), (1670, 1210),
    (1800, 1350), (1920, 1370), (2080, 1360),
]
planted_rhodo = 0
for bx, by in RHODO_SPOTS:
    height = rng.uniform(38, 60)
    if paste_sprite(image, 'rhododendron', bx, by, height, 0.10, NEAR_AIR, rng.random() < .5):
        planted_rhodo += 1
        continue
    br = rng.uniform(18, 30)
    # Foliage base
    draw.ellipse((bx - br, by - br * 0.65, bx + br, by + br * 0.65), fill=(42, 82, 58, 240))
    draw.ellipse((bx - br * 0.7, by - br * 0.85, bx + br * 0.7, by + br * 0.45), fill=(56, 102, 70, 240))
    # Blossom clusters (pink, magenta, white)
    for _ in range(rng.randint(6, 14)):
        fl_x = bx + rng.uniform(-br * 0.7, br * 0.7)
        fl_y = by + rng.uniform(-br * 0.5, br * 0.4)
        fl_color = rng.choice([(235, 150, 185, 230), (245, 180, 210, 230), (250, 235, 240, 230), (215, 120, 160, 230)])
        fl_r = rng.uniform(2.5, 5.0)
        draw.ellipse((fl_x - fl_r, fl_y - fl_r, fl_x + fl_r, fl_y + fl_r), fill=fl_color)

# Grass clumps punctuate the foreground strip; procedural strokes stay beneath.
for gx in [120, 340, 610, 905, 1850, 2140, 2330, 2480]:
    gy = rng.randrange(1390, 1432)
    paste_sprite(image, 'grass-clump', gx, gy + 8, rng.uniform(34, 52), 0.06, NEAR_AIR, rng.random() < .5)


# Pine grove anchoring the left side (painted sprites when available).
def pine(x, y, height):
    draw.line((x, y, x + height * 0.012, y - height), fill=(40, 59, 50, 255), width=max(3, int(height * 0.025)))
    for j in range(10):
        down = j * 0.091
        half = height * (0.018 + j * 0.026)
        tip = y - height + height * down
        fill = (34 + j * 2, 66 + j * 2, 57 + j)
        draw.polygon(
            [(x, tip), (x - half, tip + height * 0.18), (x - half * 0.38, tip + height * 0.15),
             (x, tip + height * 0.23), (x + half, tip + height * 0.18)],
            fill=(*fill, 255)
        )


GROVE = [(95, 1340, 430, 'pine-tall', False), (300, 1290, 300, 'pine-medium', True),
         (412, 1330, 395, 'pine-tall', True), (566, 1300, 240, 'pine-young', False),
         (645, 1338, 200, 'pine-young', True)]
for x, y, h, name, flip in GROVE:
    if not paste_sprite(image, name, x, y, h, 0.06, NEAR_AIR, flip):
        pine(x, y, h)

# Sprawling deciduous oak tree on the right.
base = (2295, 1370)
if not paste_sprite(image, 'oak-full', 2295, 1385, 410, 0.05, NEAR_AIR):
    trunk = [(2268, 1385), (2284, 1190), (2266, 1110), (2294, 990), (2312, 990), (2296, 1130), (2323, 1220), (2325, 1385)]
    draw.polygon(trunk, fill=(68, 64, 48, 255))
    branches = [(2297, 1135, 2170, 1052, 17), (2296, 1090, 2398, 991, 15), (2289, 1178, 2428, 1120, 12), (2293, 1050, 2242, 965, 12), (2288, 1154, 2118, 1132, 11)]
    for x, y, ex, ey, width in branches:
        draw.line((x, y, ex, ey), fill=(68, 64, 48, 255), width=width)
        draw.line((ex, ey, ex + (ex - x) * 0.22, ey - 42), fill=(68, 64, 48, 255), width=max(3, width // 2))

    for cx, cy, rx, ry in [(2165, 1020, 120, 75), (2260, 953, 123, 88), (2395, 977, 134, 80), (2460, 1080, 105, 74), (2125, 1113, 105, 70), (2310, 1050, 110, 72)]:
        for _ in range(23):
            angle = rng.random() * math.tau
            radius = rng.random() ** 0.5
            x = cx + math.cos(angle) * rx * radius
            y = cy + math.sin(angle) * ry * radius
            size = rng.randrange(22, 52)
            color = rng.choice([(94, 116, 65, 255), (114, 130, 70, 255), (130, 139, 75, 255), (145, 145, 80, 255), (79, 105, 63, 255)])
            draw.ellipse((x - size, y - size * 0.72, x + size, y + size * 0.72), fill=color)

# Foreground stones and mossy rocks framing bottom.
for x, y, r in [(894, 1390, 35), (967, 1424, 49), (2015, 1406, 37), (1870, 1436, 26)]:
    draw.ellipse((x - r, y - r * 0.45, x + r, y + r * 0.45), fill=(94, 110, 100, 255))
    draw.arc((x - r, y - r * 0.45, x + r, y + r * 0.45), 185, 320, fill=(143, 153, 132, 255), width=3)

ROOT.mkdir(parents=True, exist_ok=True)
image.save(ROOT / 'foreground.png', optimize=True)
used = sorted(set(SPRITE_NAMES) & set(sprites))
missing = sorted(set(SPRITE_NAMES) - set(sprites))
print(f"sprites: {len(used)}/{len(SPRITE_NAMES)} used from {SRC}"
      + (f"; procedural fallback for: {', '.join(missing)}" if missing else ''))
print(ROOT / 'foreground.png')
manifest = {
    'schemaVersion': 1,
    'id': 'woodland',
    'name': 'Woodland River & Smokies',
    'horizon': 0.72,
    'foreground': 'foreground.png',
    'description': 'An original Smokies-inspired landscape featuring layered blue ridges, a mountain stream, rustic log cabin with chimney smoke, Cades Cove split-rail fence, rhododendron blossoms, black bear family, and grazing deer under transparent animated weather.',
    'author': 'DynWall local illustration',
    'license': 'CC0-1.0'
}
(ROOT / 'manifest.json').write_text(json.dumps(manifest, indent=2) + '\n')
