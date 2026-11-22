# Realtime DynWall: native compositor constraints and contracts

## Core requirement

The current GNOME XML wallpaper slideshow cannot provide 30/60 FPS layered
weather animation. Its fixed image crossfades are presentation transitions,
not a GPU scene. Increasing its frame count wastes storage and does not add
frame-accurate time-of-day rendering.

The project should retain a **systemd --user service**, but the service needs
a compositor-compatible way to place GPU content *below desktop icons and
normal windows*.

## GNOME compatibility

- **GNOME on Wayland:** GNOME Mutter does not expose the wlr-layer-shell
  protocol to third-party clients. An ordinary systemd process cannot create
  a guaranteed wallpaper layer beneath desktop icons. An ordinary fullscreen
  window is not an acceptable substitute: it may obscure icons, intercept
  input, or appear above application windows.
- **GNOME on Xorg:** An X11 desktop-window backend can set the EWMH
  `_NET_WM_WINDOW_TYPE_DESKTOP` and `_NET_WM_STATE_BELOW` hints, though it
  must still be validated against GNOME Shell and the DING desktop-icons
  extension. It may use a service-owned accelerated SDL/OpenGL renderer.
- **Wayland with a layer-shell compositor:** A separate layer-shell backend
  may be possible, but does not make GNOME Wayland support that protocol.
- **GNOME Shell extension:** The only supported compositor-integrated path
  under GNOME Wayland is Shell-owned composition (including an extension),
  which the current project requirements explicitly exclude.

**Do not ship a systemd real-time renderer described as GNOME Wayland
compatible without verifying its actual background placement on a GNOME
Wayland session.** A service may manage state independently, but it cannot
magically grant ordinary windows wallpaper-level privileges.

## Renderer design

The weather reader and astronomical calculations should be pure, testable
modules. `dynwall_astronomy.get_sky_state()` returns observed-location sun
and moon azimuth/elevation, apparent disc diameters, illuminated fraction,
waxing direction and twilight phase. It requires PyEphem. Never hardcode
a lunar phase by day-of-month or use hour-of-day to place the sun.

Suggested scene order:

1. Dynamic sky gradient and stars
2. Accurate sun and moon discs (separate sprites)
3. Weather-driven cloud layer (drawn in front of celestial discs)
4. Distant ridges and forests with parallax
5. Independent wind-driven fog/haze layers between terrain bands
6. Foreground vegetation and cabin, including local smoke

Assets for each layer must be independent RGBA textures, dimensionally
aligned. An opaque still landscape **with a painted sun** is not a valid
source asset for an astronomical sun sprite: dimming its original sun
doesn't remove it. Obtain a sun-free landscape source before claiming
dynamic celestial position.

The astronomical sky-to-screen transform should use a configurable
view direction and horizontal/vertical field of view, account for monitor
geometry, and hide objects below the skyline. A full 360-degree azimuth
mapped indiscriminately onto a narrow wallpaper produces incorrect
positions.

Cloud occlusion must use the actual cloud alpha at the projected celestial
disc location, not just reduce disc brightness based on cloud-cover percent.
Moon illumination must use the ephemeris phase angle to clip the disc's
terminator, including waxing/waning orientation for the viewer.

## Performance verification

- Compositor placement below desktop icons and windows; no input capture
- Stable 30 FPS minimum on the target multi-monitor geometry
- Smooth scrolling/opacity changes under live wind updates, no jumps
- Sun and moon horizon crossing for multiple dates and latitudes
- Moon phase tests against reliable ephemeris dates
- Cloud alpha occluding sun/moon in the correct draw order
- No stale procedural wallpaper during settings saves
- Graceful pause on display sleep/suspend
- Rendering disabled when the user disables DynWall
