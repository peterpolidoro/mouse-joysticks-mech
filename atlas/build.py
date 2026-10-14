#!/usr/bin/env python3
"""Build the render job for atlas/render.py from the registry and the scene.

Reads atlas/components.yaml and atlas/scene.yaml, resolves every registry
entry's `gltf_nodes` globs against the node names in the glTF (an unmatched
pattern is an error), expands the per-part view, and writes atlas/job.json,
which Blender's Python reads without needing PyYAML. Also writes
docs/renders/manifest.json with the SHA-256 of every input so `--check` can say
whether the committed renders are current.

    python3 atlas/build.py                 # write atlas/job.json
    python3 atlas/build.py --check         # exit 1 if renders/manifest.json is stale
    python3 atlas/build.py --list          # print the resolved views and node matches
"""
import argparse, fnmatch, hashlib, json, pathlib, re, struct, sys
import yaml

ROOT = pathlib.Path(__file__).resolve().parent.parent
SUFFIX = re.compile(r"\.\d{3}$")


def gltf_json(path):
    with open(path, "rb") as f:
        magic, version, length = struct.unpack("<III", f.read(12))
        assert magic == 0x46546C67, f"{path} is not a GLB"
        clen, ctype = struct.unpack("<II", f.read(8))
        return json.loads(f.read(clen))


def node_names(gltf):
    return [n.get("name", "") for n in gltf["nodes"]]


def match(patterns, names):
    out = []
    for pat in patterns:
        hits = [n for n in names if fnmatch.fnmatchcase(n, pat)]
        if not hits:
            raise SystemExit(f"registry pattern matches no glTF node: {pat!r}")
        out.extend(hits)
    return sorted(set(out))


def sha256(path):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def inputs(scene):
    files = [ROOT / scene["model"], ROOT / "atlas/components.yaml", ROOT / "atlas/scene.yaml",
             ROOT / "atlas/build.py", ROOT / "atlas/render.py"]
    for b in scene.get("boards", {}).values():
        p = ROOT / b["file"]
        if p.exists():
            files.append(p)
    return {str(p.relative_to(ROOT)): sha256(p) for p in files}


def build(scene, registry, gltf):
    names = node_names(gltf)
    entries = []
    for e in registry:
        item = dict(e)
        if e.get("gltf_nodes"):
            item["nodes"] = match(e["gltf_nodes"], names)
        entries.append(item)
    views = []
    for v in scene["views"]:
        if v.get("per_part"):
            for e in entries:
                if e.get("render") and e.get("kind") == "mechanical":
                    pv = dict(v)
                    pv.pop("per_part")
                    pv["id"] = v["id"].replace("{id}", e["id"])
                    pv["entry"] = e["id"]
                    views.append(pv)
        else:
            views.append(dict(v))
    job = {
        "root": str(ROOT),
        "model": scene["model"],
        "stations": scene["stations"],
        "rig_nodes": scene.get("rig_nodes", []),
        "boards": scene.get("boards", {}),
        "board_fixes": scene.get("board_fixes", {}),
        "explode": scene["explode"],
        "render": scene["render"],
        "entries": entries,
        "views": views,
    }
    return job


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--check", action="store_true")
    ap.add_argument("--list", action="store_true")
    args = ap.parse_args()
    scene = yaml.safe_load(open(ROOT / "atlas/scene.yaml"))
    registry = yaml.safe_load(open(ROOT / "atlas/components.yaml"))
    gltf = gltf_json(ROOT / scene["model"])
    job = build(scene, registry, gltf)
    if args.check:
        man = ROOT / "docs/renders/manifest.json"
        if not man.exists():
            print("docs/renders/manifest.json missing"); return 1
        old = json.load(open(man)).get("inputs", {})
        new = inputs(scene)
        stale = [k for k in new if old.get(k) != new[k]] + [k for k in old if k not in new]
        if stale:
            print("renders stale; changed inputs:", *stale, sep="\n  "); return 1
        print("renders current"); return 0
    if args.list:
        for e in job["entries"]:
            if "nodes" in e:
                print(f"{e['id']:24s} {len(e['nodes']):3d} nodes  e.g. {e['nodes'][0]}")
        print(len(job["views"]), "views:", " ".join(v["id"] for v in job["views"]))
        return 0
    out = ROOT / "atlas/job.json"
    job["inputs"] = inputs(scene)
    out.write_text(json.dumps(job, indent=1))
    print(f"wrote {out.relative_to(ROOT)}: {len(job['entries'])} entries, {len(job['views'])} views")
    return 0


if __name__ == "__main__":
    sys.exit(main())
