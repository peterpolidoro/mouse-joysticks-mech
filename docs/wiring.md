# Wiring

What connects what. Pin-level detail stays with the device that owns it:
the joystick board's connectors and the left and right harnesses in its
repository ([harness pinouts](https://github.com/peterpolidoro/mouse-joystick-pcb/blob/v1.0/docs/harness-pinouts.md),
[interface map](https://github.com/peterpolidoro/mouse-joystick-pcb/blob/v1.0/docs/interface-map.md),
[pyControl port pinout](https://github.com/peterpolidoro/mouse-joystick-pcb/blob/v1.0/docs/pycontrol-port-pinout.md)), the rig-level
cabling of both rigs in the rig's repository ([Hardware/rig-connections.md](https://github.com/sourishmukh/joystick-rig/blob/main/Hardware/rig-connections.md),
which is private to the lab). WireViz drawings of each harness are planned.

| Cable | Board connector | Notes | Documents |
| --- | --- | --- | --- |
| [Joystick harness (motor, encoder, limit switch)](components/harness.md) | `J1102`, `J1103`, `J1601` | Left and right variants; the left swaps one coil pair and A/B so the boards and firmware are identical. Label them. | [harness-pinouts.md](https://github.com/peterpolidoro/mouse-joystick-pcb/blob/v1.0/docs/harness-pinouts.md) |
| [Brake coil lead](components/brake-lead.md) | `J1801` |  | [interface-map.md](https://github.com/peterpolidoro/mouse-joystick-pcb/blob/v1.0/docs/interface-map.md) |
| [Torque sensor lead](components/torque-lead.md) | `J2001` | Five conductors, shielded: excitation, signal pair, ground, shield. | [interface-map.md](https://github.com/peterpolidoro/mouse-joystick-pcb/blob/v1.0/docs/interface-map.md) |
| [pyControl link](components/rj45-link.md) | `J301` | Straight Ethernet patch cable; pins 1, 2, 4 and 6 used. | [pycontrol-port-pinout.md](https://github.com/peterpolidoro/mouse-joystick-pcb/blob/v1.0/docs/pycontrol-port-pinout.md) |
| [Angle and torque BNC runs](components/analog-outputs.md) | `J1101`, `J901` |  | [onebox-analog-interface.md](https://github.com/peterpolidoro/mouse-joystick-pcb/blob/v1.0/docs/onebox-analog-interface.md) |
| [36 V motor supply](components/supply-36v.md) | `J501` |  | [power.md](https://github.com/peterpolidoro/mouse-joystick-pcb/blob/v1.0/docs/power.md) |

**Label the two harnesses.** The left joystick is the mirror of the right, so
its motor and encoder cables carry two swaps; the boards and firmware are
identical and a swapped harness shows up as a motor turning the wrong way or an
encoder counting backwards.

