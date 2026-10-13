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

Frame: metres, Y up, the board lying in the XZ plane with its KiCad origin
near one corner and KiCad's top edge at small Z. `atlas/scene.yaml` places each
instance by the centre of its bounding box.
