# The joystick rig

Two motorised joysticks for a head-fixed mouse, each driven by its own
controller board under pyControl. This site is the map: turn the model,
click a part, and its page says what it is, which connector and circuit it
meets, and which firmware drives it. The numbers match the drawing below
the model.

<model-viewer id="rig" src="model/mouse-joysticks.glb" alt="The two-joystick assembly" camera-controls
 camera-orbit="-55deg 70deg auto" field-of-view="25deg" shadow-intensity="0.6" exposure="1.1"
 style="width:100%;height:540px;background:#fff;border-radius:8px">
  <button class="hotspot" slot="hotspot-lever" data-position="-0.035 0.1121 0.0121" data-normal="0 1 0" data-href="components/lever/" title="Joystick lever">1</button>
  <button class="hotspot" slot="hotspot-gear-train" data-position="-0.0137 0.0603 0.0204" data-normal="0 1 0" data-href="components/gear-train/" title="Spur gear pair">2</button>
  <button class="hotspot" slot="hotspot-motor-mount-plate" data-position="-0.0141 0.0658 0.0306" data-normal="0 1 0" data-href="components/motor-mount-plate/" title="Motor mount plate">3</button>
  <button class="hotspot" slot="hotspot-limit-switch" data-position="0.0078 0.0873 0.0291" data-normal="0 1 0" data-href="components/limit-switch/" title="Limit switch">4</button>
  <button class="hotspot" slot="hotspot-brake" data-position="-0.019 0.0772 0.0375" data-normal="0 1 0" data-href="components/brake/" title="Magnetic particle brake">5</button>
  <button class="hotspot" slot="hotspot-shaft-couplers" data-position="-0.0196 0.0781 0.0625" data-normal="0 1 0" data-href="components/shaft-couplers/" title="Shaft couplers">6</button>
  <button class="hotspot" slot="hotspot-torque-sensor" data-position="-0.0225 0.0791 0.0904" data-normal="0 1 0" data-href="components/torque-sensor/" title="Reaction torque sensor">7</button>
  <button class="hotspot" slot="hotspot-torque-sensor-plate" data-position="-0.027 0.0633 0.1154" data-normal="0 1 0" data-href="components/torque-sensor-plate/" title="Torque sensor plate">8</button>
  <button class="hotspot" slot="hotspot-dual-base-plate" data-position="0.0 -0.0048 -0.0" data-normal="0 1 0" data-href="components/dual-base-plate/" title="Dual base plate">9</button>
  <button class="hotspot" slot="hotspot-motor" data-position="-0.0187 0.0434 0.0497" data-normal="0 1 0" data-href="components/motor/" title="Stepper motor">10</button>
  <button class="hotspot" slot="hotspot-encoder" data-position="-0.0205 0.0443 0.0693" data-normal="0 1 0" data-href="components/encoder/" title="Lever-axis encoder">11</button>
  <button class="hotspot" slot="hotspot-stage-interface-plate" data-position="-0.0212 0.0275 0.0737" data-normal="0 1 0" data-href="components/stage-interface-plate/" title="Stage interface plate">12</button>
  <button class="hotspot" slot="hotspot-rotation-plate" data-position="-0.0232 0.0032 0.0883" data-normal="0 1 0" data-href="components/rotation-plate/" title="Rotation plate">13</button>
  <button class="hotspot" slot="hotspot-linear-stage" data-position="-0.0282 0.0154 0.0893" data-normal="0 1 0" data-href="components/linear-stage/" title="Linear stage">14</button>
  <button class="hotspot" slot="hotspot-rotation-lock" data-position="-0.0127 0.004 0.0926" data-normal="0 1 0" data-href="components/rotation-lock/" title="Rotation indicator and lock">15</button>
</model-viewer>
<script>
document.querySelectorAll('#rig .hotspot').forEach(b => b.addEventListener('click', () => { location.href = b.dataset.href; }));
</script>
<style>
.hotspot{width:22px;height:22px;border-radius:11px;border:2px solid #fff;background:#d9480f;color:#fff;font:bold 11px sans-serif;cursor:pointer;box-shadow:0 1px 3px rgba(0,0,0,.4)}
.hotspot:hover{background:#a63a0b}
</style>

The same view as a drawing, for a browser without WebGL or for printing;
the numbers are links:

<object data="renders/rig-iso.svg" type="image/svg+xml" style="width:100%"></object>

| # | Part | | # | Part |
| ---: | --- | --- | ---: | --- |
| 1 | [Joystick lever](components/lever.md) | | 9 | [Dual base plate](components/dual-base-plate.md) |
| 2 | [Spur gear pair](components/gear-train.md) | | 10 | [Stepper motor](components/motor.md) |
| 3 | [Motor mount plate](components/motor-mount-plate.md) | | 11 | [Lever-axis encoder](components/encoder.md) |
| 4 | [Limit switch](components/limit-switch.md) | | 12 | [Stage interface plate](components/stage-interface-plate.md) |
| 5 | [Magnetic particle brake](components/brake.md) | | 13 | [Rotation plate](components/rotation-plate.md) |
| 6 | [Shaft couplers](components/shaft-couplers.md) | | 14 | [Linear stage](components/linear-stage.md) |
| 7 | [Reaction torque sensor](components/torque-sensor.md) | | 15 | [Rotation indicator and lock](components/rotation-lock.md) |
| 8 | [Torque sensor plate](components/torque-sensor-plate.md) | |  | |

## Where to go

- [One station](station.md): the mechanism exploded, part by part.
- [Components](components/README.md): every part, board, cable and endpoint.
- [Boards](boards.md): the two circuit boards, with their own documentation.
- [Wiring](wiring.md): harnesses, leads and the cables between the devices.
- [Operate](operate.md): how a session runs, and where the operating guide is.
- [Mechanical bill of materials](bom-mechanical.md) and [the model](model.md).
- [The manual](https://github.com/peterpolidoro/mouse-joysticks-mech/releases): one PDF of these pages with the boards' and the firmware's
  documentation at their tagged revisions, attached to each release of the repository.

The mechanical design is Sam Jager's (Janelia Research Campus); the boards,
firmware and this documentation are Peter Polidoro's. Model and documents are
CC-BY-SA-4.0; see the repository.
