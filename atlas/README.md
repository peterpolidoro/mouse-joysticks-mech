# atlas/

The renders, the component pages and the viewer of this repository are
generated from the model and two YAML files here. Nothing under `docs/renders/`
or in the generated pages is edited by hand.

| File | What |
| --- | --- |
| `components.yaml` | the component registry: every part, board, cable and external endpoint of the rig, with its glTF nodes, vendor part number, datasheet, board connector, schematic block, firmware files and protocol verbs. The header explains the fields. |
| `scene.yaml` | the scene: units and frame, which glTF root is which station, where the boards stand (a placement study, not a fixture), the exploded-view step, the render settings and the camera of every view |
| `build.py` | reads both files and the glTF, resolves every registry pattern to node names (an unmatched pattern is an error), expands the per-part view and writes `job.json` for Blender; `--check` compares `docs/renders/manifest.json` with the inputs' hashes |
| `render.py` | runs inside Blender: imports the models, and per view sets the subject, ghosting, explode offsets and camera, renders a PNG and writes `docs/renders/hotspots/<view>.json` (projected pixel boxes and world centres of every registry entry) |
| `bom.py` | the mechanical bill of materials counted from the glTF through the registry, to `docs/bom-mechanical.md` and `.csv`; `--check` lists part nodes no entry covers |
| `boards/` | the two boards' glTF exports from their KiCad layouts, with `PROVENANCE.md` |

## Regenerating

Blender 4.5 and Python 3 with PyYAML; here through Guix:

```sh
python3 atlas/build.py                     # atlas/job.json
guix shell blender -- blender -b --python atlas/render.py -- atlas/job.json docs/renders/
python3 atlas/bom.py                       # docs/bom-mechanical.md
python3 atlas/pages.py && python3 atlas/site_pages.py   # docs/components/, station, index, boards, wiring, operate
python3 atlas/overlay.py docs/renders      # clickable SVG per view and its callout legend
mkdocs build && cp mouse-joysticks.glb atlas/boards/*.glb site/model/   # the site, or `pixi run site`
python3 atlas/build.py --check             # are the committed renders current?
```

A subset, at low quality, while adjusting a camera:

```sh
guix shell blender -- blender -b --python atlas/render.py -- atlas/job.json /tmp/preview --views rig-iso,part-brake --preview
```

Cycles on the CPU renders without a display. At preview quality a view takes
seconds. At the committed quality a solid view takes ten to thirty seconds
and a ghosted part view one to four minutes, because the ghost material is
transparent and Cycles follows up to 64 transparent bounces through the
station; the full set of 24 views is about 40 minutes on an eight-core
machine. Run one Blender at a time: Guix wraps the binary in a shell script,
so `pkill blender` stops the wrapper and not the render. `docs/renders/manifest.json`
records the SHA-256 of every input, and `build.py --check` reports stale
renders without rendering, so the renders regenerate only when the model,
the registry, the scene or the scripts change.

## The site

`mkdocs.yml` builds the pages under `docs/` into `site/` with the Material
theme; `pixi run site` runs every generator first and then copies the model
files (`mouse-joysticks.glb`, `atlas/boards/*.glb`) to `site/model/`, where
the front page's `<model-viewer>` loads them from the same origin. The
`.github/workflows/pages.yml` workflow does the same on every push to `main`
and deploys to GitHub Pages; it needs Pages set to "GitHub Actions" as its
source in the repository settings. `site_pages.py` writes the front page
(the viewer with one hotspot per callout of the hero view, numbered as the
overlay numbers them, and the clickable SVG for browsers without WebGL),
`boards.md`, `wiring.md` and `operate.md`; `pages.py` writes the component and
station pages. Markdown links are written relative to each page, so the same
files read on GitHub and on the site.

| File | What |
| --- | --- |
| `site_pages.py` | the site's own pages, from the registry and the hero view's hotspot file |
| `../mkdocs.yml` | site configuration: theme, navigation, the model-viewer script |
| `../pixi.toml`, `../pixi.lock` | the Python environment for every script here and for mkdocs; Blender stays outside it |
| `../.github/workflows/pages.yml` | the Pages deployment |

## Known limits of the first render set (2026-10-13)

- In the part views a light-coloured subject (the plates, the base plate,
  the couplers) has little contrast against the light backdrop and the
  ghosted context. A Freestyle outline around the subject, or a darker
  tint for the ghost, would fix it; `render.py` has neither yet.
- Large flat faces show a faint mottling from the denoiser at 96 samples.
  More samples cost render time linearly.
- The boards' FFC sockets (`J1301`, `J501`) have no library 3D model and
  are absent from the board glTFs.

## Frames

The glTF is in metres, Y up, the base plate's long axis along Z, the right
(un-mirrored) station at Z > 0. Every vector in `scene.yaml` and every
`centre_gltf` in the hotspot files is in that frame. Blender works Z up;
`render.py` converts on the way in and out. The board glTFs are metres, Y up,
board in the XZ plane; `scene.yaml` places each by the centre of its bounds.
