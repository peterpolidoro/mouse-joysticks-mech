#!/usr/bin/env python3
"""Mechanical bill of materials, counted from the glTF through the registry.

    python3 atlas/bom.py            # writes docs/bom-mechanical.md and .csv
    python3 atlas/bom.py --check    # lists glTF part nodes no registry entry covers

A registry entry with `bom: true` becomes one row per distinct part number it
names; the quantity is the number of matched glTF nodes, counted per station
and in total. The native Inventor assembly is not in this repository, so the
count is what the exported model shows and is to be checked against it.
"""
import csv, fnmatch, json, pathlib, re, struct, sys
import yaml

ROOT = pathlib.Path(__file__).resolve().parent.parent
VENDOR_URL = {
    "McMaster-Carr": "https://www.mcmaster.com/{pn}",
}


def gltf_json(path):
    with open(path, "rb") as f:
        f.read(12); clen, _ = struct.unpack("<II", f.read(8)); return json.loads(f.read(clen))


def part_nodes(gltf, scene):
    """(name, station) for every part node: children of a station root, plus scene roots."""
    nodes = gltf["nodes"]; roots = gltf["scenes"][0]["nodes"]
    station_root = {s["root"]: name for name, s in scene["stations"].items()}
    out = []
    for r in roots:
        n = nodes[r]
        if n.get("name") in station_root:
            st = station_root[n["name"]]
            for c in n.get("children", []):
                out.append((nodes[c].get("name", ""), st))
        else:
            name = n.get("name", "")
            if any(fnmatch.fnmatchcase(name, p) for p in scene["rig_nodes"]):
                out.append((name, "rig"))
            else:
                box = [[1e18] * 3, [-1e18] * 3]
                _aabb(gltf, r, _IDENT, box)
                out.append((name, "right" if (box[0][2] + box[1][2]) / 2 > 0 else "left"))
    return out


_IDENT = [[1 if r == c else 0 for c in range(4)] for r in range(4)]


def _mat(n):
    if "matrix" in n:
        m = n["matrix"]; return [[m[c * 4 + r] for c in range(4)] for r in range(4)]
    t = n.get("translation", [0, 0, 0]); x, y, z, w = n.get("rotation", [0, 0, 0, 1]); s = n.get("scale", [1, 1, 1])
    R = [[1 - 2 * (y * y + z * z), 2 * (x * y - z * w), 2 * (x * z + y * w)],
         [2 * (x * y + z * w), 1 - 2 * (x * x + z * z), 2 * (y * z - x * w)],
         [2 * (x * z - y * w), 2 * (y * z + x * w), 1 - 2 * (x * x + y * y)]]
    return [[R[r][c] * s[c] for c in range(3)] + [t[r]] for r in range(3)] + [[0, 0, 0, 1]]


def _aabb(gltf, i, M, box):
    """World axis-aligned bounds of node i and its descendants, from the accessors' min/max."""
    n = gltf["nodes"][i]
    M2 = [[sum(M[r][k] * _mat(n)[k][c] for k in range(4)) for c in range(4)] for r in range(4)]
    if "mesh" in n:
        for prim in gltf["meshes"][n["mesh"]]["primitives"]:
            a = gltf["accessors"][prim["attributes"]["POSITION"]]
            for cx in (a["min"][0], a["max"][0]):
                for cy in (a["min"][1], a["max"][1]):
                    for cz in (a["min"][2], a["max"][2]):
                        p = [sum(M2[r][c] * [cx, cy, cz][c] for c in range(3)) + M2[r][3] for r in range(3)]
                        for k in range(3):
                            box[0][k] = min(box[0][k], p[k]); box[1][k] = max(box[1][k], p[k])
    for c in n.get("children", []):
        _aabb(gltf, c, M2, box)


def main():
    check = "--check" in sys.argv
    scene = yaml.safe_load(open(ROOT / "atlas/scene.yaml"))
    reg = yaml.safe_load(open(ROOT / "atlas/components.yaml"))
    parts = part_nodes(gltf_json(ROOT / scene["model"]), scene)
    covered = set()
    rows = []
    for e in reg:
        if not e.get("bom"):
            continue
        counts = {"right": 0, "left": 0, "rig": 0}
        matched_names = set()
        for name, st in parts:
            if any(fnmatch.fnmatchcase(name, p) for p in e["gltf_nodes"]):
                counts[st] += 1; covered.add(name); matched_names.add(re.sub(r":\d+$", "", name))
        pns = [p.strip() for p in str(e.get("part_number", "")).split(",") if p.strip()]
        rows.append({"id": e["id"], "name": e["name"], "vendor": e.get("vendor", ""),
                     "part_numbers": pns, "model_names": sorted(matched_names),
                     "qty_right": counts["right"], "qty_left": counts["left"], "qty_rig": counts["rig"],
                     "qty": sum(counts.values()), "confirm": e.get("confirm", [])})
    if check:
        missing = sorted({n for n, _ in parts if n not in covered})
        print("uncovered part nodes:" if missing else "every part node is covered", *missing, sep="\n  ")
        return 1 if missing else 0
    docs = ROOT / "docs"; docs.mkdir(exist_ok=True)
    with open(docs / "bom-mechanical.csv", "w", newline="") as f:
        w = csv.writer(f); w.writerow(["id", "name", "vendor", "part_numbers", "model_names", "qty_right", "qty_left", "qty_rig", "qty"])
        for r in rows:
            w.writerow([r["id"], r["name"], r["vendor"], "; ".join(r["part_numbers"]), "; ".join(r["model_names"]), r["qty_right"], r["qty_left"], r["qty_rig"], r["qty"]])
    lines = ["# Mechanical bill of materials", "",
             "Counted from `mouse-joysticks.glb` by `atlas/bom.py` through the registry",
             "`atlas/components.yaml`; do not edit, run the script. Quantities are glTF",
             "part instances per station (the right station is the un-mirrored one). The",
             "native Inventor assembly is not in this repository, so the counts and the",
             "open questions below are to be checked against it.", "",
             "| Part | Vendor | Part number | Right | Left | Rig | Total | Model names |",
             "| --- | --- | --- | ---: | ---: | ---: | ---: | --- |"]
    for r in rows:
        pn = ", ".join(f"[{p}]({VENDOR_URL[r['vendor']].format(pn=p)})" if r["vendor"] in VENDOR_URL else f"`{p}`" for p in r["part_numbers"]) or ""
        lines.append(f"| [{r['name']}](components/{r['id']}.md) | {r['vendor']} | {pn} | {r['qty_right']} | {r['qty_left']} | {r['qty_rig']} | {r['qty']} | {', '.join(f'`{n}`' for n in r['model_names'])} |")
    qs = [(r["name"], q) for r in rows for q in r["confirm"]]
    if qs:
        lines += ["", "## To confirm", ""] + [f"- **{n}:** {q}" for n, q in qs]
    (docs / "bom-mechanical.md").write_text("\n".join(lines) + "\n")
    print(f"wrote docs/bom-mechanical.md ({len(rows)} rows) and .csv")
    return 0


if __name__ == "__main__":
    sys.exit(main())
