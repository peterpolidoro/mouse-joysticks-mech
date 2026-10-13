# atlas/

The renders, the component pages and the viewer of this repository are
generated from the model and two YAML files here. Nothing under `renders/`
or in the generated pages is edited by hand.

| File | What |
| --- | --- |
| `components.yaml` | the component registry: every part, board, cable and external endpoint of the rig, with its glTF nodes, vendor part number, datasheet, board connector, schematic block, firmware files and protocol verbs. The header explains the fields. |
| `scene.yaml` | the scene: units and frame, which glTF root is which station, where the boards stand (a placement study, not a fixture), the exploded-view step, the render settings and the camera of every view |
| `build.py` | reads both files and the glTF, resolves every registry pattern to node names (an unmatched pattern is an error), expands the per-part view and writes `job.json` for Blender; `--check` compares `renders/manifest.json` with the inputs' hashes |
| `render.py` | runs inside Blender: imports the models, and per view sets the subject, ghosting, explode offsets and camera, renders a PNG and writes `renders/hotspots/<view>.json` (projected pixel boxes and world centres of every registry entry) |
| `bom.py` | the mechanical bill of materials counted from the glTF through the registry, to `docs/bom-mechanical.md` and `.csv`; `--check` lists part nodes no entry covers |
| `boards/` | the two boards' glTF exports from their KiCad layouts, with `PROVENANCE.md` |

## Regenerating

Blender 4.5 and Python 3 with PyYAML; here through Guix:

```sh
python3 atlas/build.py                     # atlas/job.json
guix shell blender -- blender -b --python atlas/render.py -- atlas/job.json renders/
python3 atlas/bom.py                       # docs/bom-mechanical.md
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
so `pkill blender` stops the wrapper and not the render. `renders/manifest.json`
records the SHA-256 of every input, and `build.py --check` reports stale
renders without rendering, so the renders regenerate only when the model,
the registry, the scene or the scripts change.

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
