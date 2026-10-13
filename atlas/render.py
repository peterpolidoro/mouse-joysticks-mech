"""Render the atlas views with Blender, headless.

    blender -b --python atlas/render.py -- atlas/job.json renders/ [--views a,b] [--preview]

Reads the job atlas/build.py wrote (no PyYAML inside Blender), imports the
mechanism and the board models, and for every view sets the subject, the
ghosting, the explode offsets and the camera, renders a PNG and writes
renders/hotspots/<view>.json: for each registry entry visible in the view,
its projected pixel box and its world centre (in the glTF frame) for the
SVG overlays and the <model-viewer> hotspots.

Frames: the glTF is Y up; Blender imports it Z up ((x, y, z) -> (x, -z, y)).
Every vector in the job is in the glTF frame and converted here by G(); the
hotspot output is converted back by G_inv().
"""
import fnmatch, json, math, os, re, sys, time
import bpy
from mathutils import Vector, Matrix
from bpy_extras.object_utils import world_to_camera_view

SUFFIX = re.compile(r"\.\d{3}$")
C = Matrix(((1, 0, 0), (0, 0, -1), (0, 1, 0)))  # glTF -> Blender basis change


def G(v):
    return Vector((v[0], -v[2], v[1]))


def G_inv(v):
    return [v.x, v.z, -v.y]


def base(name):
    return SUFFIX.sub("", name)


def log(*a):
    print("[atlas]", *a, flush=True)


def import_glb(path):
    before = set(bpy.data.objects)
    bpy.ops.import_scene.gltf(filepath=path)
    return [o for o in bpy.data.objects if o not in before]


def ancestors(o):
    while o is not None:
        yield o
        o = o.parent


def meshes_under(tops):
    out = []
    for t in tops:
        out += [o for o in [t] + list(t.children_recursive) if o.type == "MESH"]
    return out


def world_aabb(objs):
    mn = Vector((1e18,) * 3); mx = Vector((-1e18,) * 3)
    for o in objs:
        if o.type != "MESH":
            continue
        for c in o.bound_box:
            w = o.matrix_world @ Vector(c)
            mn = Vector(map(min, mn, w)); mx = Vector(map(max, mx, w))
    return mn, mx


def gltf_rotation(deg):
    """Rotation given as X, Y, Z angles about the glTF axes, applied in that order, as a Blender matrix."""
    rx, ry, rz = [math.radians(a) for a in deg]
    R = Matrix.Rotation(rz, 3, "Z") @ Matrix.Rotation(ry, 3, "Y") @ Matrix.Rotation(rx, 3, "X")
    return C @ R @ C.inverted()


class Scene:
    def __init__(self, job, root):
        self.job = job
        self.root = root
        self.mech = import_glb(os.path.join(root, job["model"]))
        log(f"mechanism: {len(self.mech)} objects, {sum(1 for o in self.mech if o.type == 'MESH')} meshes")
        self.station_of = {}
        roots = {base(s["root"]): name for name, s in job["stations"].items()}
        for o in self.mech:
            st = None
            for a in ancestors(o):
                if base(a.name) in roots:
                    st = roots[base(a.name)]
            if st is None:
                top = list(ancestors(o))[-1]
                if any(fnmatch.fnmatchcase(base(top.name), p) for p in job["rig_nodes"]):
                    st = "rig"
                else:
                    mn, mx = world_aabb(meshes_under([top]))
                    st = "right" if -(mn.y + mx.y) / 2 > 0 else "left"
            self.station_of[o] = st
        self.entry_objs = {}
        for e in job["entries"]:
            if "nodes" not in e:
                continue
            tops = [o for o in self.mech if base(o.name) in e["nodes"]]
            if not tops:
                raise SystemExit(f"no Blender object for registry entry {e['id']}")
            self.entry_objs[e["id"]] = tops
        self.board_objs = []
        for bid, b in job["boards"].items():
            path = os.path.join(root, b["file"])
            if not os.path.exists(path) or not b.get("instances"):
                log(f"board {bid}: no file or no instances, skipped")
                continue
            for inst in b["instances"]:
                objs = import_glb(path)
                tops = [o for o in objs if o.parent is None]
                e = bpy.data.objects.new(f"board:{bid}:{inst['station']}", None)
                bpy.context.scene.collection.objects.link(e)
                for o in tops:
                    o.parent = e
                mn, mx = world_aabb(meshes_under(tops))
                scale = 0.001 if (mx - mn).length > 1.0 else 1.0
                R = gltf_rotation(inst.get("rotation_deg", [0, 0, 0])).to_4x4()
                e.matrix_world = R @ Matrix.Scale(scale, 4)
                bpy.context.view_layer.update()
                mn, mx = world_aabb(meshes_under(tops))
                e.matrix_world = Matrix.Translation(G(inst["position"]) - (mn + mx) / 2) @ e.matrix_world
                for o in meshes_under(tops):
                    self.station_of[o] = inst["station"]
                    self.board_objs.append(o)
                log(f"board {bid} at {inst['station']}: {len(tops)} top nodes, size {[round(v, 3) for v in (mx - mn)]}")
        bpy.context.view_layer.update()
        self.all_objs = [o for o in bpy.data.objects if o.type == "MESH"]
        self.orig_mats = {o: [s.material for s in o.material_slots] for o in self.all_objs}
        self.orig_matrix = {o: o.matrix_world.copy() for o in bpy.data.objects}
        self.ghost = self.make_ghost(job["render"].get("ghost_alpha", 0.07))
        self.normalise_materials(job["render"].get("materials", {}))
        self.setup_render()

    def normalise_materials(self, spec):
        """Inventor appearances arrive as PBR; polished metals have roughness 0 and read
        as mirrors of the white world. Floor the roughness and cap the metallic so every
        surface shows its form; colours are kept."""
        rmin = spec.get("roughness_min", 0.4); mmax = spec.get("metallic_max", 0.5)
        n = 0
        for m in bpy.data.materials:
            if m is self.ghost or not m.use_nodes:
                continue
            for node in m.node_tree.nodes:
                if node.type == "BSDF_PRINCIPLED":
                    r = node.inputs["Roughness"]; k = node.inputs["Metallic"]
                    if not r.is_linked and r.default_value < rmin:
                        r.default_value = rmin; n += 1
                    if not k.is_linked and k.default_value > mmax:
                        k.default_value = mmax
        log(f"materials: {len(bpy.data.materials)} total, {n} roughness floored at {rmin}")
        if spec.get("flat_shading"):
            for o in self.all_objs:
                for p in o.data.polygons:
                    p.use_smooth = False
            log("flat shading on every mesh")

    def make_ghost(self, alpha):
        m = bpy.data.materials.new("atlas_ghost"); m.use_nodes = True
        bsdf = m.node_tree.nodes["Principled BSDF"]
        bsdf.inputs["Base Color"].default_value = (0.55, 0.60, 0.68, 1)
        bsdf.inputs["Alpha"].default_value = alpha
        bsdf.inputs["Roughness"].default_value = 0.6
        try:
            m.blend_method = "BLEND"
        except Exception:
            pass
        return m

    def setup_render(self):
        r = self.job["render"]; scn = bpy.context.scene
        scn.render.engine = r.get("engine", "CYCLES")
        scn.cycles.device = "CPU"
        scn.cycles.use_denoising = True
        scn.cycles.transparent_max_bounces = 64
        scn.render.film_transparent = r.get("film_transparent", True)
        scn.render.image_settings.file_format = "PNG"
        scn.render.image_settings.color_mode = "RGBA"
        scn.view_settings.view_transform = r.get("view_transform", "Standard")
        scn.view_settings.look = "None"
        world = bpy.data.worlds.new("atlas"); world.use_nodes = True
        bg = world.node_tree.nodes["Background"]
        col = r.get("background", [1, 1, 1])
        bg.inputs[0].default_value = (col[0], col[1], col[2], 1); bg.inputs[1].default_value = r.get("world_strength", 1.0)
        scn.world = world
        sun = r.get("sun", {})
        ld = bpy.data.lights.new("sun", type="SUN"); ld.energy = sun.get("strength", 2.5)
        ld.angle = math.radians(sun.get("angle_deg", 8))
        lo = bpy.data.objects.new("sun", ld); scn.collection.objects.link(lo)
        lo.rotation_euler = G(sun.get("direction", [-0.6, 1.0, -0.4])).normalized().to_track_quat("Z", "Y").to_euler()
        cd = bpy.data.cameras.new("cam"); cd.clip_start = 0.001; cd.clip_end = 100
        self.cam = bpy.data.objects.new("cam", cd); scn.collection.objects.link(self.cam); scn.camera = self.cam

    def objs_of(self, spec, entry=None):
        if spec == "all":
            return list(self.all_objs)
        kind, _, arg = spec.partition(":")
        if kind == "station":
            return [o for o in self.all_objs if self.station_of.get(o) in (arg, "rig")]
        if kind == "entry":
            tops = [t for t in self.entry_objs[entry] if arg in ("any", self.station_of.get(t)) or self.station_of.get(t) == "rig"]
            return meshes_under(tops)
        raise SystemExit(f"unknown subject {spec}")

    def restore(self):
        for o, mats in self.orig_mats.items():
            for s, m in zip(o.material_slots, mats):
                s.material = m
        for o, m in self.orig_matrix.items():
            o.matrix_world = m
        for o in bpy.data.objects:
            o.hide_render = False
        bpy.context.view_layer.update()

    def explode(self, factor, station):
        step = self.job["explode"]["step"]
        zs = self.job["stations"][station]["z_sign"]
        for e in self.job["entries"]:
            ex = e.get("explode")
            if not ex or e["id"] not in self.entry_objs:
                continue
            d = Vector((0, 0, zs * ex["order"] * step * factor)) if ex["axis"] == "z" else Vector((0, -ex["order"] * step * factor, 0))
            for t in self.entry_objs[e["id"]]:
                if self.station_of.get(t) in (station, "rig"):
                    t.matrix_world = Matrix.Translation(G(d)) @ t.matrix_world
        bpy.context.view_layer.update()

    def frame(self, subject, cam_spec, long_side):
        mn, mx = world_aabb(subject)
        ctr = (mn + mx) / 2
        corners = [Vector((x, y, z)) for x in (mn.x, mx.x) for y in (mn.y, mx.y) for z in (mn.z, mx.z)]
        d = G(cam_spec["direction"]).normalized()
        up = G(cam_spec["up"]).normalized() if "up" in cam_spec else Vector((0, 0, 1))
        if abs(d.dot(up)) > 0.999:
            up = Vector((0, 1, 0))
        xa = up.cross(d).normalized(); ya = d.cross(xa).normalized()
        cam = self.cam; cd = cam.data
        cam.rotation_euler = Matrix((xa, ya, d)).transposed().to_euler()
        cd.type = "ORTHO" if cam_spec.get("kind") == "ortho" else "PERSP"
        cd.lens = 50; cd.sensor_fit = "AUTO"
        fill = cam_spec.get("fill", 0.9)
        radius = (mx - mn).length / 2
        dist = radius * (4 if cd.type == "PERSP" else 10)
        cam.location = ctr + d * dist
        if cd.type == "ORTHO":
            cd.ortho_scale = radius * 2
        scn = bpy.context.scene
        aspect = cam_spec.get("aspect")
        bpy.context.view_layer.update()
        for _ in range(5):
            pts = [world_to_camera_view(scn, cam, c) for c in corners]
            if aspect:
                ax = aspect[0] / aspect[1]
            else:
                w = max(p.x for p in pts) - min(p.x for p in pts); h = max(p.y for p in pts) - min(p.y for p in pts)
                ax = max(0.5, min(2.0, (w * scn.render.resolution_x) / (h * scn.render.resolution_y) if h > 0 else 1.33))
            if ax >= 1:
                scn.render.resolution_x = long_side; scn.render.resolution_y = int(round(long_side / ax))
            else:
                scn.render.resolution_y = long_side; scn.render.resolution_x = int(round(long_side * ax))
            bpy.context.view_layer.update()
            pts = [world_to_camera_view(scn, cam, c) for c in corners]
            xs = [p.x for p in pts]; ys = [p.y for p in pts]
            f = max(max(xs) - min(xs), max(ys) - min(ys)) / fill
            cx = (max(xs) + min(xs)) / 2 - 0.5; cy = (max(ys) + min(ys)) / 2 - 0.5
            landscape = scn.render.resolution_x >= scn.render.resolution_y
            if cd.type == "ORTHO":
                cd.ortho_scale *= f
                vw = cd.ortho_scale if landscape else cd.ortho_scale * scn.render.resolution_x / scn.render.resolution_y
            else:
                dist *= f
                vw = 2 * dist * math.tan(cd.angle / 2) * (1 if landscape else scn.render.resolution_x / scn.render.resolution_y)
            vh = vw * scn.render.resolution_y / scn.render.resolution_x
            ctr = ctr + xa * cx * vw + ya * cy * vh
            cam.location = ctr + d * dist
            bpy.context.view_layer.update()

    def hotspots(self, view_id, visible):
        scn = bpy.context.scene; cam = self.cam
        W, H = scn.render.resolution_x, scn.render.resolution_y
        out = {"view": view_id, "width": W, "height": H, "entries": []}
        for e in self.job["entries"]:
            if e["id"] not in self.entry_objs or not e.get("render"):
                continue
            for station in ("right", "left", "rig"):
                objs = [o for o in meshes_under([t for t in self.entry_objs[e["id"]] if self.station_of.get(t) == station]) if o in visible]
                if not objs:
                    continue
                mn, mx = world_aabb(objs)
                corners = [Vector((x, y, z)) for x in (mn.x, mx.x) for y in (mn.y, mx.y) for z in (mn.z, mx.z)]
                pts = [world_to_camera_view(scn, cam, c) for c in corners]
                xs = [p.x for p in pts]; ys = [p.y for p in pts]
                inside = sum(1 for p in pts if 0 <= p.x <= 1 and 0 <= p.y <= 1 and p.z > 0)
                box = [max(0, min(xs)) * W, (1 - min(1, max(ys))) * H, min(1, max(xs)) * W, (1 - max(0, min(ys))) * H]
                ctr = (mn + mx) / 2
                out["entries"].append({"id": e["id"], "station": station, "name": e.get("name"),
                                       "box_px": [round(v, 1) for v in box], "corners_in_frame": inside,
                                       "centre_gltf": [round(v, 4) for v in G_inv(ctr)],
                                       "size_gltf": [round(v, 4) for v in G_inv(mx - mn)]})
        return out

    def render_view(self, v, outdir, preview):
        r = self.job["render"]
        self.restore()
        entry = v.get("entry")
        hidden = set()
        if not v.get("boards"):
            hidden.update(self.board_objs)
        if v.get("hide"):
            _, _, arg = v["hide"].partition(":")
            hidden.update(o for o in self.all_objs if self.station_of.get(o) == arg)
        if v["subject"].startswith("station:"):
            st = v["subject"].split(":")[1]
            hidden.update(o for o in self.all_objs if self.station_of.get(o) not in (st, "rig"))
        for o in hidden:
            o.hide_render = True
        visible = [o for o in self.all_objs if o not in hidden]
        subject = [o for o in self.objs_of(v["subject"], entry) if o not in hidden]
        subj = set(subject)
        if v.get("others") == "ghost":
            for o in visible:
                if o not in subj:
                    if not o.material_slots:
                        o.data.materials.append(self.ghost)
                    for s in o.material_slots:
                        s.material = self.ghost
        if v.get("explode"):
            st = v["subject"].split(":")[1] if ":" in v["subject"] else "right"
            self.explode(v["explode"], st)
            frame_objs = [o for o in visible if self.station_of.get(o) in (st, "rig")]
        else:
            frame_objs = subject
        long_side = r["preview_long_side_px"] if preview else (r["hero_long_side_px"] if v.get("hero") else r["long_side_px"])
        self.frame(frame_objs, v["camera"], long_side)
        scn = bpy.context.scene
        scn.cycles.samples = r["preview_samples"] if preview else r["samples"]
        scn.render.filepath = os.path.join(outdir, v["id"] + ".png")
        t0 = time.time()
        bpy.ops.render.render(write_still=True)
        hs = self.hotspots(v["id"], set(visible))
        os.makedirs(os.path.join(outdir, "hotspots"), exist_ok=True)
        with open(os.path.join(outdir, "hotspots", v["id"] + ".json"), "w") as f:
            json.dump(hs, f, indent=1)
        log(f"{v['id']}: {scn.render.resolution_x}x{scn.render.resolution_y} in {time.time() - t0:.0f}s, {len(hs['entries'])} hotspots")


def main():
    argv = sys.argv[sys.argv.index("--") + 1:]
    job_path, outdir = argv[0], argv[1]
    only = None; preview = False; i = 2
    while i < len(argv):
        if argv[i] == "--views":
            only = argv[i + 1].split(","); i += 2
        elif argv[i] == "--preview":
            preview = True; i += 1
        else:
            raise SystemExit(f"unknown argument {argv[i]}")
    job = json.load(open(job_path))
    os.makedirs(outdir, exist_ok=True)
    bpy.ops.wm.read_factory_settings(use_empty=True)
    scene = Scene(job, job["root"])
    views = [v for v in job["views"] if only is None or v["id"] in only]
    log(f"{len(views)} views, preview={preview}")
    for v in views:
        scene.render_view(v, outdir, preview)
    if only is None and not preview:
        with open(os.path.join(outdir, "manifest.json"), "w") as f:
            json.dump({"inputs": job.get("inputs", {}), "views": [v["id"] for v in views], "blender": bpy.app.version_string}, f, indent=1)
    log("done")


if __name__ == "__main__":
    main()
