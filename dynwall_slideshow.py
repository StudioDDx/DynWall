"""GNOME native wallpaper slideshow: no GNOME Shell extension or frame-by-frame gsettings."""
from __future__ import annotations

from datetime import datetime
from pathlib import Path
import os
import tempfile
import xml.etree.ElementTree as ET


def write_slideshow(destination: Path, frames: list[Path], seconds: float, *, smooth: bool = False) -> Path:
    if not frames or not all(frame.is_file() for frame in frames):
        raise ValueError("slideshow requires existing frame images")
    if not 1.0 <= seconds <= 3600:
        raise ValueError("invalid slide duration")
    root = ET.Element("background")
    start = ET.SubElement(root, "starttime")
    now = datetime.now().astimezone()
    for tag, value in (("year", now.year), ("month", now.month), ("day", now.day),
                       ("hour", now.hour), ("minute", now.minute), ("second", now.second)):
        ET.SubElement(start, tag).text = str(value)
    for index, frame in enumerate(frames):
        slide = ET.SubElement(root, "static")
        # In smooth mode GNOME interpolates each transition continuously using
        # its compositor, rather than displaying one image for seconds at a time.
        ET.SubElement(slide, "duration").text = "0.100" if smooth else f"{seconds:.3f}"
        ET.SubElement(slide, "file").text = str(frame.resolve())
        if smooth and len(frames) > 1:
            fade = ET.SubElement(root, "transition", type="overlay")
            ET.SubElement(fade, "duration").text = f"{seconds:.3f}"
            ET.SubElement(fade, "from").text = str(frame.resolve())
            ET.SubElement(fade, "to").text = str(frames[(index + 1) % len(frames)].resolve())
    destination.parent.mkdir(parents=True, exist_ok=True)
    payload = ET.tostring(root, encoding="utf-8", xml_declaration=True)
    fd, tmp_name = tempfile.mkstemp(prefix=".dynwall-slide-", suffix=".xml", dir=destination.parent)
    try:
        with os.fdopen(fd, "wb") as stream:
            stream.write(payload)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(tmp_name, destination)
    finally:
        if os.path.exists(tmp_name):
            os.unlink(tmp_name)
    return destination
