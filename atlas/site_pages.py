#!/usr/bin/env python3
"""The atlas site's own pages: the front page with the model viewer, the
boards, the wiring and the operating pointers.

    python3 atlas/site_pages.py     # writes docs/index.md, docs/boards.md, docs/wiring.md, docs/operate.md

The front page embeds `docs/model/mouse-joysticks.glb` (the model exported
from the render pipeline with the atlas finishes, `pixi run model`; the
source glTF has only Inventor's appearance names) in Google's <model-viewer>
with one hotspot per part that has a callout on the hero render, at the
part's centre from docs/renders/hotspots/rig-iso.json and numbered as the
overlay numbers it, and below it the clickable SVG overlay for readers
without WebGL.
The model and overlay URLs carry a content hash (`?v=`), so a browser that
cached the old file (GitHub Pages allows ten minutes, and a reload does not
refetch what an <object> embeds) fetches the new one. The overlay's tag is
taken from its inputs, the PNG and the hotspot file, so it does not depend
on whether overlay.py has run before this script.
Component pages come from pages.py; this script only writes what the site
needs beyond them.
"""
import json, pathlib, sys
import yaml

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
from overlay import select_items, vtag  # noqa: E402

ROOT = pathlib.Path(__file__).resolve().parent.parent
PCB = "https://github.com/peterpolidoro/mouse-joystick-pcb"
CAM = "https://github.com/peterpolidoro/camera-gpio-interface-pcb"
MECH = "https://github.com/peterpolidoro/mouse-joysticks-mech"
FIRM = "https://github.com/peterpolidoro/mouse-joystick-firm"
RIG = "https://github.com/sourishmukh/joystick-rig"
RAW = "https://raw.githubusercontent.com/peterpolidoro"


def index(reg, by_id):
    hs = json.load(open(ROOT / "docs/renders/hotspots/rig-iso.json"))
    items = select_items(hs, "rig-iso")
    svg_v = vtag(ROOT / "docs/renders/rig-iso.png", ROOT / "docs/renders/hotspots/rig-iso.json", ROOT / "atlas/overlay.py")
    glb_v = vtag(ROOT / "docs/model/mouse-joysticks.glb")
    L = ["# The joystick rig", "",
         "Two motorised joysticks for a head-fixed mouse, each driven by its own",
         "controller board under pyControl. This site is the map: turn the model,",
         "click a part, and its page says what it is, which connector and circuit it",
         "meets, and which firmware drives it. The numbers match the drawing below", "the model.", "",
         f'<model-viewer id="rig" src="model/mouse-joysticks.glb?v={glb_v}" alt="The two-joystick assembly" camera-controls',
         ' camera-orbit="-55deg 70deg auto" field-of-view="25deg" shadow-intensity="0.6" exposure="1.1"',
         ' style="width:100%;height:540px;background:#fff;border-radius:8px">']
    for i, e in enumerate(items, 1):
        x, y, z = e["centre_gltf"]
        L.append(f'  <button class="hotspot" slot="hotspot-{e["id"]}" data-position="{x} {y} {z}" data-normal="0 1 0"'
                 f' data-href="components/{e["id"]}/" title="{e["name"]}">{i}</button>')
    L += ["</model-viewer>",
          "<script>",
          "document.querySelectorAll('#rig .hotspot').forEach(b => b.addEventListener('click', () => { location.href = b.dataset.href; }));",
          "</script>",
          "<style>",
          ".hotspot{width:22px;height:22px;border-radius:11px;border:2px solid #fff;background:#d9480f;color:#fff;font:bold 11px sans-serif;cursor:pointer;box-shadow:0 1px 3px rgba(0,0,0,.4)}",
          ".hotspot:hover{background:#a63a0b}",
          "</style>", "",
          "The same view as a drawing, for a browser without WebGL or for printing;",
          "the numbers are links:", "",
          f'<object data="renders/rig-iso.svg?v={svg_v}" type="image/svg+xml" style="width:100%"></object>', "",
          "| # | Part | | # | Part |", "| ---: | --- | --- | ---: | --- |"]
    half = (len(items) + 1) // 2
    for k in range(half):
        a = items[k]; b = items[k + half] if k + half < len(items) else None
        row = f"| {k+1} | [{a['name']}](components/{a['id']}.md) | | "
        row += f"{k+half+1} | [{b['name']}](components/{b['id']}.md) |" if b else " | |"
        L.append(row)
    L += ["", "## Where to go", "",
          "- [One station](station.md): the mechanism exploded, part by part.",
          "- [Components](components/README.md): every part, board, cable and endpoint.",
          "- [Boards](boards.md): the two circuit boards, with their own documentation.",
          "- [Wiring](wiring.md): harnesses, leads and the cables between the devices.",
          "- [Operate](operate.md): how a session runs, and where the operating guide is.",
          "- [Mechanical bill of materials](bom-mechanical.md) and [the model](model.md).",
          f"- [The manual]({MECH}/releases): one PDF of these pages with the boards' and the firmware's",
          "  documentation at their tagged revisions, attached to each release of the repository.", "",
          "The mechanical design is Sam Jager's (Janelia Research Campus); the boards,",
          "firmware and this documentation are Peter Polidoro's. Model and documents are",
          "CC-BY-SA-4.0; see the repository."]
    (ROOT / "docs/index.md").write_text("\n".join(L) + "\n")
    return len(items)


def boards(reg):
    L = ["# Boards", "",
         "The rig's two circuit boards. Each has its own repository with the schematic,",
         "the layout, the fabrication package, the generated documentation and the",
         "bring-up record; this page is the door to them. The pictures are the board",
         "repositories' own renders at the tagged revision.", ""]
    for e in reg:
        if e["kind"] != "board" or not e.get("repository"):
            continue
        repo = e["repository"]; tag = e.get("tag", "main")
        base = {"mouse-joystick-pcb": PCB, "camera-gpio-interface-pcb": CAM}[repo]
        raw = f"{RAW}/{repo}/{tag}/docs/generated/3d"
        L += [f"## {e['name']}", "", e["description"].strip(), "",
              f"![{e['name']}, isometric]({raw}/iso-front-left.png)", "",
              f"| | |", "| --- | --- |",
              f"| Repository | [{repo}]({base}) at `{tag}` |",
              f"| Where it sits | {'one per station, under the mechanism in the placement study' if e['station'] == 'both' else 'one per rig, between pyControl and the cameras (Rig 1 only)'} |",
              f"| Start with | [README]({base}/blob/{tag}/README.md), [interface map]({base}/blob/{tag}/docs/interface-map.md) |",
              f"| Generated documentation | [schematic, renders, BOM, geometry]({base}/blob/{tag}/docs/generated/README.md) |",
              f"| Fabrication | [the package the boards were ordered from]({base}/tree/{tag}/fab) |", ""]
        if repo == "mouse-joystick-pcb":
            L += ["![The two boards in place under their stations](renders/boards-in-place.png)", ""]
            L += [f"Also: the [UART protocol]({base}/blob/{tag}/docs/uart-protocol.md) pyControl speaks to it, the",
                  f"[harness pinouts]({base}/blob/{tag}/docs/harness-pinouts.md), [power]({base}/blob/{tag}/docs/power.md),",
                  f"and the [bring-up log]({base}/blob/{tag}/docs/bringup-log.md) with every measurement by board serial.",
                  f"The firmware is [mouse-joystick-firm]({FIRM}) (`v1.0.0`); its",
                  f"[architecture page]({FIRM}/blob/main/docs/architecture.md) and",
                  f"[circuit-to-code map]({FIRM}/blob/main/docs/circuit-code-map.md) say which code drives which circuit.", ""]
            L += ["![Placement study, with every board of Rig 1](renders/rig-with-boards-iso.png)", "",
                  "The boards in the placement study stand under their stations, terminal",
                  "blocks up; where they finally mount is an enclosure decision. The camera",
                  "interface board stands in their row beyond the end of the base plate only",
                  "so that one picture shows every board of Rig 1; on the rig it sits by the",
                  "cameras.", ""]
    (ROOT / "docs/boards.md").write_text("\n".join(L) + "\n")


def wiring(reg, by_id):
    L = ["# Wiring", "",
         "What connects what. Pin-level detail stays with the device that owns it:",
         f"the joystick board's connectors and the left and right harnesses in its",
         f"repository ([harness pinouts]({PCB}/blob/v1.0/docs/harness-pinouts.md),",
         f"[interface map]({PCB}/blob/v1.0/docs/interface-map.md),",
         f"[pyControl port pinout]({PCB}/blob/v1.0/docs/pycontrol-port-pinout.md)), the rig-level",
         f"cabling of both rigs in the rig's repository ([Hardware/rig-connections.md]({RIG}/blob/main/Hardware/rig-connections.md),",
         f"which is private to the lab, with its WireViz cable drawing [Hardware/cables.svg]({RIG}/blob/main/Hardware/cables.svg):",
         "every run between devices and the cable BOM). WireViz drawings of the two station harnesses are planned in the board repository.", "",
         "| Cable | Board connector | Notes | Documents |", "| --- | --- | --- | --- |"]
    for e in reg:
        if e["kind"] != "cable":
            continue
        conns = ", ".join(f"`{c['connector']}`" for c in e.get("connects_to", []))
        docs = ", ".join(f"[{d.split('/')[-1]}]({PCB}/blob/v1.0/{d.split('/', 1)[1]})" for d in e.get("docs", []) if d.startswith("mouse-joystick-pcb/"))
        L.append(f"| [{e['name']}](components/{e['id']}.md) | {conns} | {(e.get('description') or '').strip()} | {docs} |")
    L += ["", "**Label the two harnesses.** The left joystick is the mirror of the right, so",
          "its motor and encoder cables carry two swaps; the boards and firmware are",
          "identical and a swapped harness shows up as a motor turning the wrong way or an",
          "encoder counting backwards.", ""]
    (ROOT / "docs/wiring.md").write_text("\n".join(L) + "\n")


def operate(reg):
    L = ["# Operate", "",
         "How a session runs, in one paragraph, and where the full guide is.", "",
         "pyControl on the rig PC uploads the trial task to the controller; the task",
         "talks to one joystick board per session. Each trial: the joystick moves to",
         "the presented angle, the brake sets and the motor lets go, the torque reading",
         "is zeroed, the board watches for a pull or a push, a pull opens the reward",
         "solenoid, one second after the outcome the board sends its trial summary, the",
         "joystick parks, and after the pause the next trial starts. A fault, a refused",
         "command or a reply that never comes ends the session with the motor rail off.", "",
         f"![One trial]({RAW}/mouse-joystick-firm/main/docs/diagrams/trial-sequence.svg)", "",
         "## Documents", "",
         f"- **The researcher guide** in the rig's repository: how to set up the pyControl GUI, the variables, what the log means, what to do when a joystick does not answer. The repository is private to the lab: [notes/261007_mouse_joystick_researcher_guide.md]({RIG}/blob/main/notes/261007_mouse_joystick_researcher_guide.md).",
         f"- [Glossary]({FIRM}/blob/main/docs/glossary.md): the words the protocol, the task and the log use.",
         f"- [Architecture]({FIRM}/blob/main/docs/architecture.md): what runs where, from the rig PC to the parts of a station.",
         f"- [The pyControl device class]({FIRM}/blob/main/docs/pycontrol-api.md): the methods a task can call.",
         f"- [The UART protocol]({PCB}/blob/v1.0/docs/uart-protocol.md): every verb, reply, event and fault code.",
         f"- [Reprogramming a board]({FIRM}/blob/v1.0.0/README.md#reprogramming-a-v10-board) and [setting up a controller]({FIRM}/blob/v1.0.0/pycontrol/README.md).", ""]
    (ROOT / "docs/operate.md").write_text("\n".join(L) + "\n")


def main():
    reg = yaml.safe_load(open(ROOT / "atlas/components.yaml"))
    by_id = {e["id"]: e for e in reg}
    n = index(reg, by_id); boards(reg); wiring(reg, by_id); operate(reg)
    print(f"wrote docs/index.md ({n} hotspots), docs/boards.md, docs/wiring.md, docs/operate.md")


if __name__ == "__main__":
    sys.exit(main())
