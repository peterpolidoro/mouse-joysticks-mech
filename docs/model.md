# The model

`mouse-joysticks.stp` and `mouse-joysticks.glb` are one export of Sam Jager's
Inventor 2025 assembly `Dual Lever Assembly` (2026-07-22). The STEP is the
geometry to measure or modify; the glTF is what the renders and the viewer
load, and it carries the assembly tree with the Inventor product names as
node names.

## Frame and units

| | |
| --- | --- |
| Units | metres (glTF); the STEP is in millimetres |
| Up | +Y |
| Long axis of the base plate | Z |
| Right station (un-mirrored) | Z > 0, root node `GEAR DRIVEN SINGLE LEVER:1` |
| Left station (mirrored; `MOTOR MOUNT PLATE_MIR`, `DRIVEN SPUR GEAR MIR`) | Z < 0, root node `GEAR DRIVEN SINGLE LEVER:2` |
| Whole assembly | X −0.099 to 0.050, Y −0.010 to 0.140, Z −0.182 to 0.182 |
| Base plate | 349 × 76 × 10 mm, top face at Y = 0 |
| Lever axis | Y ≈ 0.078, X ≈ −0.015, running along Z |
| Motor axis | Y ≈ 0.043 |

The levers point up and toward each other at the centre of the base plate;
the motors are outboard. Each station slides along Z on its linear stage and
rotates on its rotation plate.

## Tree

Nine scene roots: the base plate, the two station assemblies (48 and 49
nodes), and per station a rotation indicator, a lock knob and its screw.
Under each station: the purchased parts by vendor part number (Lin
Engineering motor, Placid brake, Transducer Techniques torque sensor, US
Digital encoder, Omron switch, Misumi stage, McMaster and ServoCity
hardware) and the custom plates, gears, couplers and the lever. The
[registry](https://github.com/peterpolidoro/mouse-joysticks-mech/blob/main/atlas/components.yaml) groups them and the
[mechanical BOM](bom-mechanical.md) counts them.

## What the model does not record

- The controller boards and their mounting. The renders place them as the
  2026-09-21 placement study did; the enclosure decision is open.
- Cables and harnesses.
- How the brake and torque sensor leads are dressed; the parts themselves
  are modelled.
- Materials and finishes beyond Inventor's appearance names.

## Opening it

- **FreeCAD**: File → Import the STEP; the tree keeps the product names.
- **Blender**: File → Import → glTF 2.0; Blender converts to Z up on import.
- **A browser**: any glTF viewer takes the `.glb`; the atlas page in this
  repository embeds it with `<model-viewer>` and hotspots.
