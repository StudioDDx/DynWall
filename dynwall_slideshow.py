"""GNOME native wallpaper slideshow: no GNOME Shell extension or frame-by-frame gsettings."""
from __future__ import annotations

from datetime import datetime
from pathlib import Path
import os
import tempfile
import xml.etree.ElementTree as ET


def write_slideshow(destination: Path, frames: list[Path], seconds: float) -> Path:
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
    # Use static slides rather than GNOME's optional crossfades: no bright flashes
    # and no need to render intermediate frames.
    for frame in frames:
        slide = ET.SubElement(root, "static")
        ET.SubElement(slide, "duration").text = f"{seconds:.3f}"
        ET.SubElement(slide, "file").text = str(frame.resolve())
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
