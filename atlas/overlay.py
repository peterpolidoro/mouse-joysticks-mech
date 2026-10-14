#!/usr/bin/env python3
"""Clickable SVG overlays and callout legends from the hotspot files.

    python3 atlas/overlay.py docs/renders/ [--view rig-iso] [--link '../components/{id}/']

For every docs/renders/hotspots/<view>.json (or the one named), writes
docs/renders/<view>.svg: the PNG as the image, one numbered callout per registry
entry in frame with a link to its page, and the legend as a Markdown table in
docs/renders/<view>.callouts.md. The default link is the site's page for
the part, relative to the SVG's place under docs/renders/. On a rig view the left station's parts are the
mirror of the right's, so only the right station and the rig-level parts are
numbered; a station or part view numbers what it shows. The image reference
carries the PNG's content hash as a query (`<view>.png?v=...`): GitHub Pages
caches every file for ten minutes and a reload does not refetch what an
embedded SVG loads, so a changed render must be a new URL.
"""
import argparse, hashlib, json, pathlib, sys


def vtag(*paths):
    """A short content hash of the files, for cache-busting URLs; empty if one is missing."""
    h = hashlib.sha256()
    for p in paths:
        p = pathlib.Path(p)
        if not p.exists():
            return ""
        h.update(p.read_bytes())
    return h.hexdigest()[:12]


def select_items(hs, view):
    """The entries a view gets callouts for, in reading order: in frame, one per id,
    and on a rig view only the right station and the rig-level parts."""
    rig_view = view.startswith("rig-")
    seen = set(); items = []
    for e in hs["entries"]:
        if e["corners_in_frame"] < 8:
            continue
        if rig_view and e["station"] == "left":
            continue
        if e["id"] in seen:
            continue
        seen.add(e["id"]); items.append(e)
    items.sort(key=lambda e: (e["box_px"][1], e["box_px"][0]))
    return items


def overlay(view_dir, view, link):
    hs = json.load(open(view_dir / "hotspots" / f"{view}.json"))
    W, H = hs["width"], hs["height"]
    items = select_items(hs, view)
    r = max(9, round(min(W, H) * 0.016))
    tag = vtag(view_dir / f"{view}.png")
    lines = [f'<svg xmlns="http://www.w3.org/2000/svg" xmlns:xlink="http://www.w3.org/1999/xlink" viewBox="0 0 {W} {H}" width="{W}" height="{H}">',
             "<style>.hs rect{fill:transparent;stroke:transparent;stroke-width:2}.hs:hover rect{stroke:#d9480f;fill:rgba(217,72,15,.08)}"
             ".hs text{font:bold %dpx sans-serif;fill:#fff;text-anchor:middle;dominant-baseline:central;pointer-events:none}.hs circle{fill:#d9480f;stroke:#fff;stroke-width:1.5}</style>" % int(r * 1.1),
             f'<image href="{view}.png{"?v=" + tag if tag else ""}" width="{W}" height="{H}"/>']
    for i, e in enumerate(items, 1):
        x0, y0, x1, y1 = e["box_px"]
        href = link.format(id=e["id"], station=e["station"])
        lines.append(f'<a class="hs" xlink:href="{href}" href="{href}"><title>{e["name"]}</title>'
                     f'<rect x="{x0:.0f}" y="{y0:.0f}" width="{x1-x0:.0f}" height="{y1-y0:.0f}"/>'
                     f'<circle cx="{x0+r:.0f}" cy="{y0+r:.0f}" r="{r}"/><text x="{x0+r:.0f}" y="{y0+r:.0f}">{i}</text></a>')
    lines.append("</svg>")
    (view_dir / f"{view}.svg").write_text("\n".join(lines) + "\n")
    md = ["| # | Part | Page |", "| ---: | --- | --- |"] + [f"| {i} | {e['name']} | [{e['id']}]({link.format(id=e['id'], station=e['station'])}) |" for i, e in enumerate(items, 1)]
    (view_dir / f"{view}.callouts.md").write_text("\n".join(md) + "\n")
    return len(items)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("renders"); ap.add_argument("--view"); ap.add_argument("--link", default="../components/{id}/")
    a = ap.parse_args()
    d = pathlib.Path(a.renders)
    views = [a.view] if a.view else sorted(p.stem for p in (d / "hotspots").glob("*.json"))
    for v in views:
        print(f"{v}: {overlay(d, v, a.link)} callouts")


if __name__ == "__main__":
    sys.exit(main())
