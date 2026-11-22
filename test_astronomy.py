"""Ephemeris contract tests for independent celestial sprites."""
from datetime import datetime, timezone
import importlib.util
import math
import unittest

from dynwall_astronomy import get_sky_state


@unittest.skipUnless(importlib.util.find_spec("ephem"), "python3-ephem not installed")
class AstronomyTests(unittest.TestCase):
    def test_day_and_night_solar_altitude(self):
        lat, lon = 35.95, -83.92
        midday = get_sky_state(lat, lon, datetime(2026, 6, 21, 16, tzinfo=timezone.utc))
        midnight = get_sky_state(lat, lon, datetime(2026, 6, 21, 4, tzinfo=timezone.utc))
        self.assertGreater(midday.sun.elevation_deg, 50)
        self.assertLess(midnight.sun.elevation_deg, -10)
        self.assertTrue(midday.sun.visible)
        self.assertFalse(midnight.sun.visible)

    def test_moon_is_bounded_and_moves_with_time(self):
        lat, lon = 35.95, -83.92
        a = get_sky_state(lat, lon, datetime(2026, 11, 21, 0, tzinfo=timezone.utc))
        b = get_sky_state(lat, lon, datetime(2026, 11, 21, 6, tzinfo=timezone.utc))
        self.assertTrue(0 <= a.moon.illuminated_fraction <= 1)
        self.assertTrue(0 <= a.moon.phase_angle_deg < 360)
        self.assertTrue(0 <= a.moon.azimuth_deg < 360)
        self.assertNotAlmostEqual(a.moon.elevation_deg, b.moon.elevation_deg, places=1)
        self.assertTrue(0.3 < a.moon.angular_diameter_deg < 0.7)
        self.assertTrue(0.3 < a.sun.angular_diameter_deg < 0.7)

    def test_invalid_locations_and_naive_dates(self):
        for lat, lon in ((91, 0), (0, -181), (float("nan"), 0), (True, 0)):
            with self.subTest(lat=lat, lon=lon), self.assertRaises(ValueError):
                get_sky_state(lat, lon)
        with self.assertRaises(ValueError):
            get_sky_state(35.95, -83.92, datetime(2026, 11, 21))


if __name__ == "__main__":
    unittest.main()
