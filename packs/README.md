# Local landscape packs

Woodland River is an original 2560×1440 illustrated foreground authored locally
with Pillow. It includes layered hills, a river meadow, a pine grove, and an open
canopy oak. The sky is transparent so the production native sky animates behind
it. No artwork downloads or model keys were used. Rebuild it with:

```sh
/usr/bin/python3 packs/author_woodland.py
```

A pack is a directory, or a ZIP archive with these files at its root (one enclosing
folder is also accepted):

```text
manifest.json
foreground.png
```

```json
{
  "schemaVersion": 1,
  "id": "my-landscape",
  "name": "My landscape",
  "horizon": 0.72,
  "foreground": "foreground.png",
  "author": "Local artist",
  "license": "Your artwork license"
}
```

The machine-readable contract is [manifest.schema.json](manifest.schema.json).
All five fields above `author` are required; `author`, `license`, `description`
and an editor's `$schema` string are optional. Unknown fields, invalid metadata,
and duplicate JSON keys are rejected rather than silently losing information.
`schemaVersion` is version `1` (`1.0` is equivalent under JSON Schema and is
canonicalized to integer `1` on import; booleans and strings are invalid). The
foreground must be a static PNG. Paths may
include subfolders and use `/` separators; `.`, `..` and empty path components
are invalid. The importer verifies the image bytes and file limits in addition
to the JSON structure.

To create a scene, author `foreground.png` and this manifest, then select
**Custom landscapes → Import folder** or **Import ZIP** in Settings. Importing
selects the pack in the current settings form; **Save** applies that selection to
the live wallpaper. Preview can show it before saving. There is no separate
"Create scene" importer: the generated `scene.json` cache, an AI art-direction
JSON spec, and a landscape-pack manifest are different formats. A v1 pack does
not define its own sky, particles, shaders, animation frames or weather physics;
those continue to come from the renderer. Unsupported fields must not be used to
imply capabilities the importer cannot render.

The horizon is a fraction measured downward from the top of the image. It must be
between 0.1 and 0.95. Transparent PNG cutouts preserve branches and treetops above
the horizon. Importing an opaque photograph automatically makes the area above
its marked horizon transparent; use an alpha cutout for an irregular skyline.
Images are stretched across the panoramic desktop, matching built-in scenes.

Import uses the native settings controls and copies validated assets into
`$XDG_DATA_HOME/dynwall/packs/<id>` (default `~/.local/share/dynwall/packs`). Existing
ids are never overwritten. Export produces a ZIP archive, regardless of the
chosen filename extension. Optional author, license, and description metadata
survive import/export. Built-in packs are read-only application assets; imported
copies have private file permissions.

Manifests are limited to 16 KiB; PNGs to 32 MiB, 8192 pixels per side and 32 million
pixels total. Archives contain at most eight entries and 32 MiB plus manifest
space when expanded. Absolute paths, parent traversal, symlinks, corrupt images,
and unsupported manifests are rejected before publication. Missing or invalid
packs are omitted from the settings catalog and renderers retain built-in terrain.
