"""Astronomical sun/moon state for independently composited celestial sprites.

All positions are topocentric and account for the observer's location and date.
Requires PyEphem (python3-ephem); never invents a moon phase if it is missing.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
import math


@dataclass(frozen=True)
class BodyState:
    azimuth_deg: float
    elevation_deg: float
    visible: bool
    angular_diameter_deg: float


@dataclass(frozen=True)
class MoonState(BodyState):
    illuminated_fraction: float
    waxing: bool
    phase_angle_deg: float


@dataclass(frozen=True)
class SkyState:
    sun: BodyState
    moon: MoonState
    sky_phase: str


def _deg(angle) -> float:
    return math.degrees(float(angle))


def get_sky_state(latitude: float, longitude: float,
                  when: datetime | None = None) -> SkyState:
    if any(isinstance(v, bool) or not isinstance(v, (float, int))
           or not math.isfinite(v) for v in (latitude, longitude)):
        raise ValueError("latitude and longitude must be finite numbers")
    if not -90 <= latitude <= 90 or not -180 <= longitude <= 180:
        raise ValueError("latitude/longitude outside WGS84 bounds")
    try:
        import ephem
    except ImportError as exc:
        raise RuntimeError("Install python3-ephem for accurate sun and moon data") from exc

    when = datetime.now(timezone.utc) if when is None else when
    if when.tzinfo is None:
        raise ValueError("when must be timezone-aware")
    when = when.astimezone(timezone.utc)
    observer = ephem.Observer()
    observer.lat = str(latitude)
    observer.lon = str(longitude)
    observer.pressure = 0  # geometric horizon without local refraction assumptions
    observer.date = when
    sun = ephem.Sun(observer)
    moon = ephem.Moon(observer)
    sun_elevation = _deg(sun.alt)
    moon_elevation = _deg(moon.alt)

    # Lunar phase angle calculated from the geocentric ecliptic longitudes.
    # Phase difference 0 = new, 180 = full, 360 = next new.
    sun_ecliptic = ephem.Ecliptic(sun)
    moon_ecliptic = ephem.Ecliptic(moon)
    phase_angle = (_deg(moon_ecliptic.lon) - _deg(sun_ecliptic.lon)) % 360
    illuminated = min(1.0, max(0.0, float(moon.phase) / 100))

    if sun_elevation >= -0.833:
        phase = "day"
    elif sun_elevation >= -6:
        phase = "civil-twilight"
    elif sun_elevation >= -12:
        phase = "nautical-twilight"
    elif sun_elevation >= -18:
        phase = "astronomical-twilight"
    else:
        phase = "night"
    return SkyState(
        sun=BodyState(
            azimuth_deg=_deg(sun.az),
            elevation_deg=sun_elevation,
            visible=sun_elevation > -0.833,
            angular_diameter_deg=_deg(sun.size) / 60,
        ),
        moon=MoonState(
            azimuth_deg=_deg(moon.az),
            elevation_deg=moon_elevation,
            visible=moon_elevation > -0.3,
            angular_diameter_deg=_deg(moon.size) / 60,
            illuminated_fraction=illuminated,
            waxing=phase_angle < 180,
            phase_angle_deg=phase_angle,
        ),
        sky_phase=phase,
    )
