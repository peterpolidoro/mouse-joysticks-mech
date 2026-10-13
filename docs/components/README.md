# Components

One page per thing in the rig a reader can point at, generated from the
registry `atlas/components.yaml`. The [station page](../station.md) shows how the
mechanical parts stack.

## Mechanical, per station

- [Joystick lever](lever.md): The lever the mouse holds. Rides on the lever axis at the front of the station; a pull moves it toward decreasing angle on both stations.
- [Spur gear pair](gear-train.md): Driving gear on the motor shaft, driven gear on the lever axis. The mirrored station has its own driven gear. The gear ratio is the number the firmware's angle scaling depends on.
- [Stepper motor](motor.md): The motor that presents, parks and homes the lever through the gear pair. Rated 0.6 A per phase; the firmware runs it below that.
- [Lever-axis encoder](encoder.md): Optical kit encoder. Its A and B channels reach the board's encoder input and are counted by the TMC5130A, not by the RP2040; the firmware reads the count over SPI.
- [Limit switch](limit-switch.md): Subminiature basic switch with a lever actuator at the positive end of travel. The firmware homes against it and uses it as the hardware stop for negative motion through the driver's reference input.
- [Magnetic particle brake](brake.md): On the lever axis behind the gear. The board's current sink drives its coil from 0 to about 49 mA to set the resistance the mouse feels while the lever is released.
- [Reaction torque sensor](torque-sensor.md): 350 ohm bridge, 1.5 mV/V, 5 in-oz, at the rear of the lever axis. The board excites it, amplifies it, samples it at 1 kHz and puts a copy on the torque BNC. The left station reads a pull negative where the right reads positive.
- [Shaft couplers](shaft-couplers.md): Two couplers on the lever axis: one between the gear and the brake, one between the brake and the torque sensor.
- [Lever-axis bearings](lever-axis-bearings.md): A ball bearing and a sleeve bearing carrying the lever axis.
- [Motor mount plate](motor-mount-plate.md): Vertical plate at the front of the station carrying the motor and the front of the lever axis; mirrored on the left station.
- [Torque sensor plate](torque-sensor-plate.md): Vertical plate at the rear of the station carrying the torque sensor.
- [Frame standoffs and spacers](frame-standoffs.md): Standoffs and spacers tying the two vertical plates to the stage interface plate.
- [Stage interface plate](stage-interface-plate.md): Horizontal plate between the linear stage carriage and the station's frame.
- [Linear stage](linear-stage.md): Base and carriage. Lets the whole station slide along the base plate's long axis to set the lever's distance from the mouse.
- [Rotation plate](rotation-plate.md): Plate under the linear stage that rotates on the base plate to set the station's angle; the indicator and lock knob read and hold it.
- [Rotation indicator and lock](rotation-lock.md): The pointer, the pivot shoulder screw and the knob that locks the rotation plate.
- [Dual base plate](dual-base-plate.md): The common base both stations rotate and slide on; 349 by 76 mm.
- [ServoCity shaft hardware](servocity-parts.md): Hubs and pattern hardware on the lever axis and gears.
- [Fasteners](fasteners.md): Socket head screws and a hex nut.

## Boards

- [Joystick controller board](joystick-board.md): One per station: RP2040, TMC5130A driver, brake current sink, torque bridge, angle and torque analog outputs, pyControl UART on an RJ-45. Placement in the renders follows the 2026-09-21 placement study and is not a fixture.
- [Camera GPIO interface board](camera-board.md): Between pyControl and the three Blackfly S cameras; strobes and sync to the OneBox. Rig 1 only.
- [pyControl controller](pycontrol-controller.md): pyboard PYBv1.1 on a Breakout 1.2; left joystick on port 1, right on port 4, solenoid on port 5.

## Cables

- [Joystick harness (motor, encoder, limit switch)](harness.md): Left and right variants; the left swaps one coil pair and A/B so the boards and firmware are identical. Label them.
- [Brake coil lead](brake-lead.md)
- [Torque sensor lead](torque-lead.md): Five conductors, shielded: excitation, signal pair, ground, shield.
- [pyControl link](rj45-link.md): Straight Ethernet patch cable; pins 1, 2, 4 and 6 used.
- [Angle and torque BNC runs](analog-outputs.md)
- [36 V motor supply](supply-36v.md)

## External

- [Neuropixels OneBox](onebox.md): Records the eight BNCs at 30 kHz; the analog copies are the sub-millisecond record.
- [Blackfly S cameras](cameras.md): Triggered at 150 Hz through the camera interface board.
- [Acquisition PC](acquisition-pc.md): pyControl GUI, SpikeGLX, the camera scripts; every board's USB.

