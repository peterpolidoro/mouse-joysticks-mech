# mouse-joysticks-mech

Mechanical model of the dual lever assembly in the Janelia Dudman lab
joystick rig: the two mirrored joystick mechanisms that the rig's two
[mouse-joystick-pcb](https://github.com/peterpolidoro/mouse-joystick-pcb)
controller boards drive, one board per joystick. The model is exported
geometry only.

| File | Format | Size | Use |
| --- | --- | --- | --- |
| `mouse-joysticks.stp` | STEP AP214 | 22.6 MB | Open in FreeCAD, Fusion, Inventor, SolidWorks or Onshape to measure, mate against or modify |
| `mouse-joysticks.glb` | glTF 2.0 binary | 11.3 MB | Open in any glTF viewer or in Blender to look at the assembly |

The assembly was modelled in Autodesk Inventor 2025 and exported to STEP on
2026-07-22; the STEP header records the file as `Dual Lever Assembly.stp`.
The native Inventor files are not in this repository.

## How The Boards Relate To It

The left mechanism is a mirror of the right one. The controller boards and
their firmware are identical for both joysticks; the reversal is made in the
motor and encoder cables, which [the harness pinouts](https://github.com/peterpolidoro/mouse-joystick-pcb/blob/main/docs/harness-pinouts.md)
in the board repository describe. Where the controller boards mount is an
enclosure decision, not something this model fixes; the boards' outlines,
mounting holes and connector positions are in their generated documentation.
The model predates the brake and torque sensor interfaces on the v1.0
controller board and does not record how those parts mount.

## Related Repositories

- [mouse-joystick-pcb](https://github.com/peterpolidoro/mouse-joystick-pcb): the joystick controller board, its protocol and its bring-up log.
- [mouse-joystick-firm](https://github.com/peterpolidoro/mouse-joystick-firm): the board's firmware and the pyControl device class.
- [camera-gpio-interface-pcb](https://github.com/peterpolidoro/camera-gpio-interface-pcb): the rig's camera interface board.
- [joystick-rig](https://github.com/sourishmukh/joystick-rig): the rig's pyControl tasks, hardware definition and operating notes.

## License

CC-BY-SA-4.0; see [LICENSE](LICENSE).

## Citation

[CITATION.cff](CITATION.cff) carries the citation metadata; GitHub renders it
under "Cite this repository".
