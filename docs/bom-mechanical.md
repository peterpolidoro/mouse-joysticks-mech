# Mechanical bill of materials

Counted from `mouse-joysticks.glb` by `atlas/bom.py` through the registry
`atlas/components.yaml`; do not edit, run the script. Quantities are glTF
part instances per station (the right station is the un-mirrored one). The
native Inventor assembly is not in this repository, so the counts and the
open questions below are to be checked against it.

| Part | Vendor | Part number | Right | Left | Rig | Total | Model names |
| --- | --- | --- | ---: | ---: | ---: | ---: | --- |
| [Joystick lever](components/lever.md) | Janelia (custom) |  | 1 | 1 | 0 | 2 | `MCL LEVER` |
| [Spur gear pair](components/gear-train.md) | Janelia (custom) |  | 1 | 2 | 0 | 3 | `DRIVEN SPUR GEAR MIR`, `Spur Gears` |
| [Stepper motor](components/motor.md) | Lin Engineering | `208-13-01D` | 1 | 1 | 0 | 2 | `LIN ENGINEERING 208-13-01D` |
| [Lever-axis encoder](components/encoder.md) | US Digital | `E4T-200-157-S-H-M-B` | 1 | 1 | 0 | 2 | `US DIGITAL E4T-200-157-S-H-M-B` |
| [Limit switch](components/limit-switch.md) | Omron | `D2F-01FL` | 1 | 1 | 0 | 2 | `D2F_01FL` |
| [Magnetic particle brake](components/brake.md) | Placid Industries | `B5Z-1R` | 1 | 1 | 0 | 2 | `PLACID INDUSTRIES B5Z-1R` |
| [Reaction torque sensor](components/torque-sensor.md) | Transducer Techniques | `RTS-5` | 1 | 1 | 0 | 2 | `TransducerTechniquesRTS5` |
| [Shaft couplers](components/shaft-couplers.md) | Janelia (custom) |  | 2 | 2 | 0 | 4 | `Coupler-SensorSide`, `CouplerBrakeSide` |
| [Lever-axis bearings](components/lever-axis-bearings.md) | McMaster-Carr | [57155K316](https://www.mcmaster.com/57155K316), [1677K313](https://www.mcmaster.com/1677K313) | 2 | 2 | 0 | 4 | `MCMASTER 1677K313_Ultra-Low-Friction Oil-Embedded Sleeve Bearing`, `MCMASTER 57155K316_Ball Bearing` |
| [Motor mount plate](components/motor-mount-plate.md) | Janelia (custom) |  | 1 | 1 | 0 | 2 | `MOTOR MOUNT PLATE`, `MOTOR MOUNT PLATE_MIR` |
| [Torque sensor plate](components/torque-sensor-plate.md) | Janelia (custom) |  | 1 | 1 | 0 | 2 | `TORQUE SENSOR PLATE` |
| [Frame standoffs and spacers](components/frame-standoffs.md) | McMaster-Carr | [93330A541](https://www.mcmaster.com/93330A541), [92510A421](https://www.mcmaster.com/92510A421), [91125A431](https://www.mcmaster.com/91125A431) | 9 | 9 | 0 | 18 | `MCMASTER 91125A431_Female Threaded Round Standoff`, `MCMASTER 92510A421_Aluminum Unthreaded Spacer`, `MCMASTER 93330A541_Female Threaded Round Standoff` |
| [Stage interface plate](components/stage-interface-plate.md) | Janelia (custom) |  | 1 | 1 | 0 | 2 | `STAGE INTERFACE PLATE` |
| [Linear stage](components/linear-stage.md) | Misumi | `XSLC60` | 1 | 1 | 0 | 2 | `MISUMI XSLC60` |
| [Rotation plate](components/rotation-plate.md) | Janelia (custom) |  | 1 | 1 | 0 | 2 | `ROTATION PLATE` |
| [Rotation indicator and lock](components/rotation-lock.md) | McMaster-Carr, Janelia (custom) | `94052A133`, `92196A537`, `90298A149` | 4 | 4 | 0 | 8 | `MCMASTER 90298A149_18-8 Stainless Steel Shoulder Screw`, `MCMASTER 92196A537_18-8 Stainless Steel Socket Head Screw`, `MCMASTER 94052A133_Screw-Head Mount Knob`, `ROTATION INDICATOR` |
| [Dual base plate](components/dual-base-plate.md) | Janelia (custom) |  | 0 | 0 | 1 | 1 | `DUAL BASE PLATE` |
| [ServoCity shaft hardware](components/servocity-parts.md) | ServoCity (goBILDA) | `1314-0016-0004`, `1314-0016-0125`, `1203-0001-0001` | 6 | 6 | 0 | 12 | `1203-0001-0001`, `SERVO CITY 1314-0016-0004`, `SERVO CITY 1314-0016-0125` |
| [Fasteners](components/fasteners.md) | McMaster-Carr | [92196A112](https://www.mcmaster.com/92196A112), [91292A117](https://www.mcmaster.com/91292A117), [92196A144](https://www.mcmaster.com/92196A144), [92196A066](https://www.mcmaster.com/92196A066), [92196A022](https://www.mcmaster.com/92196A022), [90730A005](https://www.mcmaster.com/90730A005) | 16 | 16 | 0 | 32 | `90730A005_18-8 Stainless Steel Narrow Hex Nut`, `92196A022_18-8 Stainless Steel Socket Head Screw`, `92196A066_18-8 Stainless Steel Socket Head Screw`, `92196A144_18-8 Stainless Steel Socket Head Screw`, `MCMASTER 91292A117_18-8 Stainless Steel Socket Head Screw`, `MCMASTER 92196A112_18-8 Stainless Steel Socket Head Screw` |

## To confirm

- **Joystick lever:** Material and finish of the lever (not in the model).
- **Spur gear pair:** Tooth counts of the driving and driven gears, to check against src/Conversions.hpp.
- **Lever-axis encoder:** The model names a 200 CPR disk (E4T-200) while the bring-up log confirms 1000 CPR against 51200 microsteps per revolution; which part is fitted?
- **Linear stage:** Full Misumi part number (travel and options).
- **ServoCity shaft hardware:** What each of the three ServoCity part numbers is and does.
