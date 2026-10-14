# atlas/

The renders, the component pages and the viewer of this repository are
generated from the model and two YAML files here. Nothing under `docs/renders/`
or in the generated pages is edited by hand.

| File | What |
| --- | --- |
| `components.yaml` | the component registry: every part, board, cable and external endpoint of the rig, with its glTF nodes, vendor part number, datasheet, board connector, schematic block, firmware files and protocol verbs. The header explains the fields. |
| `scene.yaml` | the scene: units and frame, which glTF root is which station, where the boards stand (a placement study, not a fixture), the exploded-view step, the studio lighting, the palette of finishes (`looks`) and the camera of every view |
| `build.py` | reads both files and the glTF, resolves every registry pattern to node names (an unmatched pattern is an error), expands the per-part view and writes `job.json` for Blender; `--check` compares `docs/renders/manifest.json` with the inputs' hashes |
| `render.py` | runs inside Blender (the `bpy` wheel or a Blender binary): imports the models, gives every part its finish, lights the studio, and per view sets the subject, the isolation, the explode offsets (from the parts' bounding boxes, so that neighbours clear each other by `explode.gap`), the floor and the camera, renders a PNG and writes `docs/renders/hotspots/<view>.json` (projected pixel boxes and world centres of every registry entry); `--model` exports the assembled model with these finishes as `docs/model/mouse-joysticks.glb` for the site's viewer |
| `bom.py` | the mechanical bill of materials counted from the glTF through the registry, to `docs/bom-mechanical.md` and `.csv`; `--check` lists part nodes no entry covers |
| `boards/` | the two boards' glTF exports from their KiCad layouts, the FFC socket mesh that stands in for their missing model, with `PROVENANCE.md` |
| `step2obj.py` | FreeCAD script that tessellates a STEP model to OBJ, one group per solid; made the socket mesh |

## Regenerating

Everything runs through pixi. The default environment holds the generators
and mkdocs; the `render` environment adds Blender 4.5 itself as the official
`bpy` wheel from PyPI, with Cycles and OpenImageDenoise, so no Blender has to
be installed (the Guix `blender` package renders too, but it lacks the
denoiser and its output is grainy).

```sh
pixi run render                            # every view into docs/renders, about an hour
pixi run preview rig-iso,part-brake        # low-quality versions of named views into tmp/preview
pixi run render-views boards-in-place      # full-quality renders of named views only, into docs/renders
pixi run model                             # the viewer's model with the atlas finishes, docs/model/mouse-joysticks.glb
pixi run generate                          # BOM, pages, overlays
pixi run site                              # the site into site/
pixi run check                             # are the renders current, is every part node covered?
```

A view takes two to three minutes at the committed quality (the hero at its
larger size a little longer), a preview fifteen seconds.
`docs/renders/manifest.json` records the SHA-256 of every input, and
`check` reports stale renders without rendering, so the renders regenerate
only when the model, the registry, the scene or the scripts change. When a
change touches only some views (a camera, a view's own switches),
`render-views` re-renders those alone and updates the manifest; it also
records them, and `check` lists them, as a reminder that the other renders
predate the current inputs until the next full render.

## The look

Finishes are not the model's. Inventor's appearance names put a white
"Steel" on the black gears, "Walnut" on the limit switch and a blue plate
where the real one is machined aluminium, so every registry entry carries a
`look` from the palette in `scene.yaml`, read off photographs of the real
stations (2026-10-13): aluminium plates, rods and end caps; black motor,
brake and torque-sensor bodies; black gears; stainless lever and screws.
`looks_by_material` and `looks_by_node` refine a part with several finishes
(the brake's aluminium end caps on its black housing, the motor's shaft).
Anything the registry does not name falls back to `material_looks`, a map
from appearance name to look.

The studio is three area lights placed on the mechanism's bounding sphere, a
darkish neutral world so polished metal reflects mid-grey rather than white,
and a floor set just under the lowest visible part of each view. Exposure
sits at -0.8 EV, with the lights and the world turned down with it: the first
render sets had half their pixels above 230 of 255 and the machined
aluminium in the photographs is a matte mid-grey. The film is
transparent and the floor a shadow catcher, so every picture carries its
contact shadows onto whatever background the page has: white on GitHub's
light theme and on the site, which puts each render on a white card. AgX tone
mapping with the medium-high-contrast look, adaptive sampling to 256 samples,
OpenImageDenoise with albedo and normal passes.

An isolation view (`others: isolate`) keeps the subject in its finish, turns
every other visible part into an unlit flat grey silhouette, and draws
Freestyle outlines: dark and thicker around the subject, thin and light
around the context. That reads for a black gear and an aluminium plate
alike, and costs nothing in noise or time. Context parts that stand between
the camera and the subject (found by casting rays from the camera to sample
points on the subject, `render.py occluders`) are drawn as ghosts at
`isolate.ghost_opacity` instead, with their outlines kept, so the brake is
seen through the couplers and torque sensor rather than hidden behind them.

## The site

`mkdocs.yml` builds the pages under `docs/` into `site/` with the Material
theme; `pixi run site` runs every generator first. The front page's
`<model-viewer>` loads `docs/model/mouse-joysticks.glb`, the model exported
from the render pipeline with the atlas finishes (`pixi run model`, and
every full render writes it too), since the source glTF carries only
Inventor's appearance names; mkdocs copies it to `site/model/` with the
pages. The
`.github/workflows/pages.yml` workflow does the same on every push to `main`
and deploys to GitHub Pages; it needs Pages set to "GitHub Actions" as its
source in the repository settings. `site_pages.py` writes the front page
(the viewer with one hotspot per callout of the hero view, numbered as the
overlay numbers them, or the clickable SVG where WebGL is missing, where the
viewer fails to load and in print: an inline script picks one),
`boards.md`, `wiring.md` and `operate.md`; `pages.py` writes the component and
station pages. Markdown links are written relative to each page, so the same
files read on GitHub and on the site. GitHub Pages serves every file with a
ten-minute cache, and a reload does not refetch what an `<object>` embeds,
so the front page's model file, its overlay and the PNG inside the overlay
carry a content hash in their URLs (`?v=`): a changed render is a new URL
and shows at once.

| File | What |
| --- | --- |
| `site_pages.py` | the site's own pages, from the registry and the hero view's hotspot file |
| `../mkdocs.yml` | site configuration: theme, navigation, the model-viewer script |
| `../pixi.toml`, `../pixi.lock` | the Python environment for every script here and for mkdocs; Blender stays outside it |
| `../.github/workflows/pages.yml` | the Pages deployment |

## Known limits (2026-10-13)

- The finishes are read off two photographs; parts not visible in them
  (the linear stage, the base plate, the couplers' exact finish, the
  ServoCity hardware) are assumed aluminium. Correct the registry's `look`
  fields and re-render.
- The boards' FFC sockets (`J1301`, `J501`) carry no model in the board
  exports; the library's STEP of the socket, tessellated once to
  `boards/FH12-50S-0.5SVA-54.obj`, stands in (`board_fixes.proxies` in
  `scene.yaml`). The board glTFs carry KiCad's 3D-viewer default materials,
  not the boards' finishes: the solder mask is a translucent green over a
  yellowish body and the RJ-45 and BNC models have no material at all.
  `board_fixes.material_looks` replaces the mask, silkscreen and body
  materials by colour match with opaque looks (dark green, label white,
  FR4), `missing_material_look` gives the colourless connector meshes
  nickel, and the few remaining pure whites are capped to a light grey.
  Copper is not in the export, so the mask is one flat green.

## Frames

The glTF is in metres, Y up, the base plate's long axis along Z, the right
(un-mirrored) station at Z > 0. Every vector in `scene.yaml` and every
`centre_gltf` in the hotspot files is in that frame. Blender works Z up;
`render.py` converts on the way in and out. The board glTFs are metres, Y up,
board in the XZ plane; `scene.yaml` places each by the centre of its bounds.
