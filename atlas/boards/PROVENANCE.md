# Board models

glTF exports of the boards, taken from the board repositories' generated
documentation (`docs/generated/3d/<board>.glb`, written by `make docs` there
with the kicad-libs material palette in its materials: opaque solder mask,
body and silkscreen looks, nickel on the connector shells whose vendor models
carry no colour, every connector present), so the renders and the viewer load
the model each board publishes and the atlas fixes nothing about it.
`pixi run boards` (`atlas/boards.py`) copies them from the sibling checkouts,
or downloads them at a tag with `--ref`, and rewrites this file.

| File | Repository | Revision | Model | Taken |
| --- | --- | --- | --- | --- |
| `camera-gpio-interface-pcb.glb` | [peterpolidoro/camera-gpio-interface-pcb](https://github.com/peterpolidoro/camera-gpio-interface-pcb) (`camera-board` in scene.yaml) | `e38f8ce` | 4.0 MB, 29 materials (29 with the palette's record), KiCad `10.0.6`, generated 2026-10-14, sha256 `6dcd387cd702` | 2026-10-14 |
| `mouse-joystick-pcb.glb` | [peterpolidoro/mouse-joystick-pcb](https://github.com/peterpolidoro/mouse-joystick-pcb) (`joystick-board` in scene.yaml) | `v1.0-7-g516ed12` | 8.4 MB, 43 materials (43 with the palette's record), KiCad `10.0.6`, generated 2026-10-14, sha256 `3c0f45928eea` | 2026-10-14 |

Frame: metres, Y up, the board lying in the XZ plane with its KiCad origin
near one corner and KiCad's top edge at small Z. `atlas/scene.yaml` places each
instance by the centre of its bounding box.
