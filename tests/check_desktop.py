#!/usr/bin/env python3
"""Validate rendered desktop-icon and context-menu screenshot evidence."""

from __future__ import annotations

import argparse
from pathlib import Path

from PIL import Image, ImageChops


def changed_pixels(
    before: Image.Image, after: Image.Image, threshold: int = 18, ignore_top: int = 0
) -> tuple[int, tuple[int, int, int, int] | None]:
    if before.size != after.size:
        raise AssertionError(f"Screenshot sizes differ: {before.size} != {after.size}")

    difference = ImageChops.difference(before.convert("RGB"), after.convert("RGB"))
    channels = difference.split()
    maximum = ImageChops.lighter(ImageChops.lighter(channels[0], channels[1]), channels[2])
    mask = maximum.point(lambda value: 255 if value >= threshold else 0)
    if ignore_top:
        mask = mask.crop((0, ignore_top, mask.width, mask.height))
    histogram = mask.histogram()
    box = mask.getbbox()
    if box is not None and ignore_top:
        box = (box[0], box[1] + ignore_top, box[2], box[3] + ignore_top)
    return histogram[255], box


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("baseline", type=Path)
    parser.add_argument("icon", type=Path)
    parser.add_argument("menu", type=Path)
    parser.add_argument("--pointer-x", type=int, required=True)
    parser.add_argument("--pointer-y", type=int, required=True)
    args = parser.parse_args()

    baseline = Image.open(args.baseline)
    icon = Image.open(args.icon)
    menu = Image.open(args.menu)

    icon_right = min(300, baseline.width)
    icon_pixels, icon_box = changed_pixels(
        baseline.crop((0, 40, icon_right, baseline.height)),
        icon.crop((0, 40, icon_right, icon.height)),
    )
    if icon_box is not None:
        icon_box = (icon_box[0], icon_box[1] + 40, icon_box[2], icon_box[3] + 40)
    if icon_pixels < 250:
        raise AssertionError(
            f"Desktop fixture is not visibly rendered: only {icon_pixels} changed pixels"
        )
    if icon_box is None:
        raise AssertionError("Desktop fixture produced no visible bounding box")

    menu_pixels, menu_box = changed_pixels(icon, menu, ignore_top=40)
    if menu_pixels < 2_000:
        raise AssertionError(
            f"Desktop context menu is not visibly rendered: only {menu_pixels} changed pixels"
        )
    if menu_box is None:
        raise AssertionError("Desktop context menu produced no visible bounding box")
    if menu_pixels > (menu.width * max(1, menu.height - 40)) // 4:
        raise AssertionError(
            "Secondary click changed the desktop instead of rendering a localized menu: "
            f"pixels={menu_pixels}, box={menu_box}"
        )

    x0 = max(0, args.pointer_x - 32)
    y0 = max(0, args.pointer_y - 32)
    x1 = min(menu.width, args.pointer_x + 520)
    y1 = min(menu.height, args.pointer_y + 380)
    local_icon = icon.crop((x0, y0, x1, y1))
    local_menu = menu.crop((x0, y0, x1, y1))
    local_pixels, _ = changed_pixels(local_icon, local_menu)
    if local_pixels < 1_000:
        raise AssertionError(
            "Desktop context menu did not visibly render near the secondary-click point: "
            f"only {local_pixels} changed pixels"
        )
    outside_pixels = menu_pixels - local_pixels
    if outside_pixels > max(20_000, local_pixels // 2):
        raise AssertionError(
            "Secondary click caused unrelated desktop changes outside the menu: "
            f"menu-local={local_pixels}, outside={outside_pixels}"
        )

    print(
        "Desktop fixture and real secondary-click menu pixels: PASS "
        f"(icon={icon_pixels} {icon_box}, menu={menu_pixels} {menu_box}, local={local_pixels})"
    )


if __name__ == "__main__":
    main()
