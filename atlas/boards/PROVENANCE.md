# Board models

glTF exports of the two boards' KiCad layouts, copied here so the renders and
the viewer load everything from one place. Regenerate with `make glb` in the
PCB repository (it writes `tmp/glb/<board>.glb` through the managed KiCad
shell, where the library's 3D models resolve) and copy the file here; the
`tag` column is what the registry (`atlas/components.yaml`) cites.

| File | Source | Tag / commit | Exported |
| --- | --- | --- | --- |
| `mouse-joystick-pcb.glb` | mouse-joystick-pcb `kicad/mouse-joystick-pcb.kicad_pcb` | `v1.0` (`55b9224`) | 2026-10-13, KiCad 10.0.6 `kicad-cli pcb export glb --subst-models --include-silkscreen --include-soldermask`; 471 meshes, every connector except the FFC socket `J1301`, which has no library model |
| `camera-gpio-interface-pcb.glb` | camera-gpio-interface-pcb `kicad/camera-gpio-interface-pcb.kicad_pcb` | `22995d1` (the `v1.0` fabrication commit is `5ddb425`; the board file is unchanged between them) | 2026-10-13, same exporter; 250 meshes, every connector except the FFC socket `J501` |

| `FH12-50S-0.5SVA-54.obj` | kicad-libs `3dmodels/orb_weaver.3dshapes/mechanical/FH12-50S-0.5SVA-54.step` (the library's in-house model, 2026-09-28) | kicad-libs working tree, 2026-10-13 | `atlas/step2obj.py` under FreeCAD 1.1.3: 54 solids (housing, actuator, 50 leads, 2 fittings), 2588 facets, millimetres in KiCad's model frame |

Frame: metres, Y up, the board lying in the XZ plane with its KiCad origin
near one corner and KiCad's top edge at small Z. `atlas/scene.yaml` places each
instance by the centre of its bounding box.

The FFC socket is absent from both board exports because the boards placed
the footprint before 2026-09-29, when the library footprint moved to the
in-house model, and their placed copies still carry the old model path; the
library's refresh of the placed footprints will fix the exports, and until
then `render.py` stands the OBJ in at the footprint's position and rotation
(`board_fixes.proxies` in `scene.yaml`).
