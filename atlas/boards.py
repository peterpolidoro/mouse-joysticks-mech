#!/usr/bin/env python3
"""The boards' models, taken from the board repositories, and their provenance.

    python3 atlas/boards.py [--ref TAG_OR_COMMIT] [--checkouts DIR]      # pixi run boards

Each board publishes `docs/generated/3d/<board>.glb` in its repository: the model `make docs` writes there from the
KiCad layout, with the kicad-libs material palette written into its materials (opaque mask, body and silkscreen
looks, nickel on the connector shells whose vendor STEP files carry no colour, the FFC socket present since the
library's model path fix, 2026-10-14). This script copies that file for every board `atlas/scene.yaml` places into
atlas/boards/, so the renders and the viewer load the model the board publishes and the atlas fixes nothing about
it, and rewrites atlas/boards/PROVENANCE.md with what was taken: the repository, its revision (the sibling
checkout's `git describe`, marked when the model is uncommitted there), the model's size, material count and the
KiCad version its documentation manifest records.

By default the files come from the sibling checkouts beside this repository (`../<board>/`); `--ref` downloads them
from GitHub at that tag or commit instead, for a machine without the checkouts. Standard library plus PyYAML.
"""
import argparse
import datetime
import hashlib
import json
import pathlib
import struct
import subprocess
import sys
import urllib.request

import yaml

ROOT = pathlib.Path(__file__).resolve().parent.parent
OWNER = "peterpolidoro"
MODEL_PATH = "docs/generated/3d/{board}.glb"
MANIFEST_PATH = "docs/generated/manifest.json"
PROVENANCE = ROOT / "atlas" / "boards" / "PROVENANCE.md"

HEADER = """# Board models

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
"""

FOOTER = """
Frame: metres, Y up, the board lying in the XZ plane with its KiCad origin
near one corner and KiCad's top edge at small Z. `atlas/scene.yaml` places each
instance by the centre of its bounding box.
"""


def sha256(data):
    return hashlib.sha256(data).hexdigest()


def glb_summary(data):
    """(material count, materials carrying the palette's record) of a binary glTF's JSON chunk."""
    if data[:4] != b"glTF":
        raise SystemExit("not a binary glTF")
    (length,) = struct.unpack("<I", data[12:16])
    doc = json.loads(data[20:20 + length])
    materials = doc.get("materials", [])
    recorded = sum(1 for m in materials if (m.get("extras") or {}).get("orb_weaver"))
    return len(materials), recorded


def git(checkout, *args):
    return subprocess.run(["git", "-C", str(checkout), *args], check=True, capture_output=True, text=True).stdout.strip()


def from_checkout(board, checkouts):
    checkout = pathlib.Path(checkouts) / board
    model = checkout / MODEL_PATH.format(board=board)
    if not model.is_file():
        raise SystemExit(f"{model} is missing; run `make docs` in {checkout}")
    revision = git(checkout, "describe", "--tags", "--always")
    dirty = git(checkout, "status", "--porcelain", "--", MODEL_PATH.format(board=board))
    manifest_path = checkout / MANIFEST_PATH
    manifest = json.loads(manifest_path.read_text(encoding="utf-8")) if manifest_path.is_file() else {}
    return model.read_bytes(), f"`{revision}`" + (", the model uncommitted there" if dirty else ""), manifest


def from_github(board, ref):
    base = f"https://raw.githubusercontent.com/{OWNER}/{board}/{ref}/"

    def fetch(path):
        with urllib.request.urlopen(urllib.request.Request(base + path, headers={"User-Agent": "mouse-joysticks-mech atlas"}), timeout=120) as r:
            return r.read()

    data = fetch(MODEL_PATH.format(board=board))
    try:
        manifest = json.loads(fetch(MANIFEST_PATH))
    except Exception:  # noqa: BLE001  (an older revision without the manifest)
        manifest = {}
    return data, f"`{ref}` (GitHub)", manifest


def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("--ref", help="download from GitHub at this tag or commit instead of copying from the sibling checkouts")
    ap.add_argument("--checkouts", default=str(ROOT.parent), help="where the board checkouts are (default: beside this repository)")
    a = ap.parse_args()
    scene = yaml.safe_load(open(ROOT / "atlas" / "scene.yaml"))
    rows = []
    for bid, b in sorted(scene.get("boards", {}).items()):
        target = ROOT / b["file"]
        board = target.stem
        data, revision, manifest = from_github(board, a.ref) if a.ref else from_checkout(board, a.checkouts)
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(data)
        materials, recorded = glb_summary(data)
        model = (f"{len(data) / 1e6:.1f} MB, {materials} materials ({recorded} with the palette's record), "
                 f"KiCad `{manifest.get('kicad_cli_version', '?')}`, generated {manifest.get('generated_at', '?')[:10]}, sha256 `{sha256(data)[:12]}`")
        rows.append(f"| `{target.name}` | [{OWNER}/{board}](https://github.com/{OWNER}/{board}) (`{bid}` in scene.yaml) | {revision} | {model} | {datetime.date.today().isoformat()} |")
        print(f"{bid}: {target.relative_to(ROOT)} from {board} at {revision}: {model}")
    PROVENANCE.write_text(HEADER + "\n".join(rows) + "\n" + FOOTER, encoding="utf-8")
    print(f"wrote {PROVENANCE.relative_to(ROOT)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
