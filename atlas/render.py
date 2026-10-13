"""Render the atlas views with Blender, headless.

Look: every mechanism part gets a finish from scene.yaml's palette through the
registry (read off photographs of the real parts), a three-light studio with a
matte floor, AgX tone mapping; isolation views draw the subject in its finish
with a dark outline over unlit grey silhouettes of the rest (Freestyle).

    blender -b --python atlas/render.py -- atlas/job.json docs/renders/ [--views a,b] [--preview]
    python atlas/render.py atlas/job.json docs/renders/ [--views a,b] [--preview]   # with the bpy wheel

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
        self.orig_matrix = {o: o.matrix_world.copy() for o in bpy.data.objects}
        self.looks = {}
        self.apply_looks(job["render"])
        self.setup_render()
        self.setup_studio()
        self.setup_isolation()

    # ------------------------------------------------------------ materials

    def look_material(self, name):
        """One Blender material per look, made on first use."""
        if name in self.looks:
            return self.looks[name]
        spec = self.job["render"]["looks"][name]
        m = bpy.data.materials.new(f"look:{name}"); m.use_nodes = True
        bsdf = m.node_tree.nodes["Principled BSDF"]
        b = spec["base"]
        bsdf.inputs["Base Color"].default_value = (b[0], b[1], b[2], 1)
        bsdf.inputs["Metallic"].default_value = spec.get("metallic", 0.0)
        bsdf.inputs["Roughness"].default_value = spec.get("roughness", 0.5)
        self.looks[name] = m
        return m

    def apply_looks(self, r):
        """Give every mechanism mesh a look: the registry entry's, with its
        per-material and per-node overrides, else the Inventor appearance's
        fallback. The board models keep their own materials."""
        by_mat = r.get("material_looks", {})
        entry_of = {}
        for e in self.job["entries"]:
            for t in self.entry_objs.get(e["id"], []):
                for o in meshes_under([t]):
                    entry_of[o] = (e, t)
        n_entry = n_fallback = 0
        for o in self.mech:
            if o.type != "MESH":
                continue
            e, top = entry_of.get(o, (None, None))
            for slot in o.material_slots:
                orig = slot.material.name if slot.material else ""
                orig = SUFFIX.sub("", orig)
                look = None
                if e:
                    look = e.get("look")
                    for pat, lk in (e.get("looks_by_node") or {}).items():
                        if any(fnmatch.fnmatchcase(base(a.name), pat) for a in ancestors(o)):
                            look = lk
                    look = (e.get("looks_by_material") or {}).get(orig, look)
                if look:
                    n_entry += 1
                else:
                    look = by_mat.get(orig, "grey-plastic"); n_fallback += 1
                slot.material = self.look_material(look)
            if not o.material_slots:
                o.data.materials.append(self.look_material((e or {}).get("look") or "grey-plastic"))
        # the boards: KiCad's materials, with only the mirror finishes tamed
        for o in self.board_objs:
            for slot in o.material_slots:
                m = slot.material
                if m and m.use_nodes:
                    for node in m.node_tree.nodes:
                        if node.type == "BSDF_PRINCIPLED" and not node.inputs["Roughness"].is_linked:
                            node.inputs["Roughness"].default_value = max(node.inputs["Roughness"].default_value, 0.3)
        self.orig_mats = {o: [sl.material for sl in o.material_slots] for o in self.all_objs}
        log(f"looks: {n_entry} slots from the registry, {n_fallback} from the appearance fallback, {len(self.looks)} looks")
        self.context_mat = bpy.data.materials.new("atlas_context"); self.context_mat.use_nodes = True
        nt = self.context_mat.node_tree
        for node in list(nt.nodes):
            if node.type != "OUTPUT_MATERIAL":
                nt.nodes.remove(node)
        em = nt.nodes.new("ShaderNodeEmission")
        c = r.get("isolate", {}).get("context_color", [0.72, 0.73, 0.75])
        em.inputs["Color"].default_value = (c[0], c[1], c[2], 1); em.inputs["Strength"].default_value = 1.0
        nt.links.new(em.outputs[0], nt.nodes["Material Output"].inputs["Surface"])

    # --------------------------------------------------------------- studio

    def setup_render(self):
        r = self.job["render"]; scn = bpy.context.scene
        scn.render.engine = r.get("engine", "CYCLES")
        scn.cycles.device = "CPU"
        scn.cycles.use_adaptive_sampling = True
        scn.cycles.adaptive_threshold = r.get("adaptive_threshold", 0.01)
        # The denoiser enum reads as empty in background mode even when the
        # build has OpenImageDenoise, so try to set it and believe the result.
        try:
            scn.cycles.denoiser = "OPENIMAGEDENOISE"
            scn.cycles.use_denoising = True
            scn.cycles.denoising_input_passes = "RGB_ALBEDO_NORMAL"
            scn.cycles.denoising_prefilter = "ACCURATE"
            log("denoiser: OpenImageDenoise")
        except Exception:
            scn.cycles.use_denoising = False
            log("WARNING: this Blender build has no denoiser (the Guix package lacks OpenImageDenoise); "
                "renders will be grainy. Use `pixi run render`, whose Blender is the official wheel.")
        scn.render.film_transparent = r.get("film_transparent", False)
        scn.render.image_settings.file_format = "PNG"
        scn.render.image_settings.color_mode = "RGBA" if scn.render.film_transparent else "RGB"
        scn.view_settings.view_transform = r.get("view_transform", "AgX")
        try:
            scn.view_settings.look = r.get("look", "None")
        except Exception as ex:
            log(f"look: {ex}"); scn.view_settings.look = "None"
        scn.view_settings.exposure = r.get("exposure", 0.0)
        world = bpy.data.worlds.new("atlas"); world.use_nodes = True
        bg = world.node_tree.nodes["Background"]
        w = r.get("world", {}); col = w.get("color", [0.45, 0.45, 0.47])
        bg.inputs[0].default_value = (col[0], col[1], col[2], 1); bg.inputs[1].default_value = w.get("strength", 0.6)
        scn.world = world
        cd = bpy.data.cameras.new("cam"); cd.clip_start = 0.001; cd.clip_end = 100
        self.cam = bpy.data.objects.new("cam", cd); scn.collection.objects.link(self.cam); scn.camera = self.cam

    def setup_studio(self):
        """Three area lights around the whole mechanism; the floor is placed per view."""
        r = self.job["render"]; scn = bpy.context.scene
        mn, mx = world_aabb([o for o in self.mech if o.type == "MESH"])
        ctr = (mn + mx) / 2; R = (mx - mn).length / 2
        self.scene_centre, self.scene_radius = ctr, R
        scale = (R / 0.2) ** 2
        self.lights = []
        for name, spec in r.get("studio", {}).items():
            ld = bpy.data.lights.new(f"light:{name}", type="AREA")
            ld.shape = "SQUARE"; ld.size = spec["size"] * R; ld.energy = spec["watts"] * scale
            lo = bpy.data.objects.new(f"light:{name}", ld); scn.collection.objects.link(lo)
            d = G(spec["direction"]).normalized()
            lo.location = ctr + d * spec["distance"] * R
            lo.rotation_euler = d.to_track_quat("Z", "Y").to_euler()
            self.lights.append(lo)
        f = r.get("floor", {})
        fm = bpy.data.materials.new("atlas_floor"); fm.use_nodes = True
        bsdf = fm.node_tree.nodes["Principled BSDF"]
        c = f.get("color", [0.46, 0.47, 0.49])
        bsdf.inputs["Base Color"].default_value = (c[0], c[1], c[2], 1)
        bsdf.inputs["Roughness"].default_value = f.get("roughness", 0.9)
        bsdf.inputs["Metallic"].default_value = 0.0
        me = bpy.data.meshes.new("floor"); size = f.get("size_factor", 40) * R
        me.from_pydata([(-size, -size, 0), (size, -size, 0), (size, size, 0), (-size, size, 0)], [], [(0, 1, 2, 3)])
        me.materials.append(fm)
        self.floor = bpy.data.objects.new("floor", me); scn.collection.objects.link(self.floor)
        log(f"studio: R={R:.3f} m, {len(self.lights)} lights, floor {size:.1f} m")

    def setup_isolation(self):
        """Collections Freestyle selects by, and the two line sets."""
        scn = bpy.context.scene; r = self.job["render"].get("isolate", {})
        self.coll_subject = bpy.data.collections.new("atlas_subject"); scn.collection.children.link(self.coll_subject)
        self.coll_context = bpy.data.collections.new("atlas_context"); scn.collection.children.link(self.coll_context)
        scn.render.line_thickness_mode = "ABSOLUTE"
        fs = bpy.context.view_layer.freestyle_settings
        fs.crease_angle = math.radians(r.get("crease_angle_deg", 110))
        fs.use_culling = True
        for ls in list(fs.linesets):
            fs.linesets.remove(ls)
        for name, coll, spec in (("subject", self.coll_subject, r.get("subject_line", {})), ("context", self.coll_context, r.get("context_line", {}))):
            ls = fs.linesets.new(name)
            ls.select_by_collection = True; ls.collection = coll; ls.collection_negation = "INCLUSIVE"
            ls.select_silhouette = True; ls.select_border = True; ls.select_crease = True
            ls.select_edge_mark = False; ls.select_contour = False; ls.select_external_contour = False
            c = spec.get("color", [0.1, 0.1, 0.1])
            ls.linestyle.color = (c[0], c[1], c[2]); ls.linestyle.thickness = spec.get("thickness", 1.0)
            ls.linestyle.alpha = 1.0
        scn.render.use_freestyle = False

    def set_isolation(self, on, subject, visible):
        scn = bpy.context.scene
        for coll in (self.coll_subject, self.coll_context):
            for o in list(coll.objects):
                coll.objects.unlink(o)
        scn.render.use_freestyle = bool(on)
        if not on:
            return
        subj = set(subject)
        for o in visible:
            (self.coll_subject if o in subj else self.coll_context).objects.link(o)
            if o not in subj:
                for sl in o.material_slots:
                    sl.material = self.context_mat
                if not o.material_slots:
                    o.data.materials.append(self.context_mat)

    def place_floor(self, objs):
        mn, mx = world_aabb(objs)
        self.floor.location = Vector((self.scene_centre.x, self.scene_centre.y, mn.z - 0.0005))
        bpy.context.view_layer.update()

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
        self.set_isolation(v.get("others") == "isolate", subject, visible)
        if v.get("explode"):
            st = v["subject"].split(":")[1] if ":" in v["subject"] else "right"
            self.explode(v["explode"], st)
            frame_objs = [o for o in visible if self.station_of.get(o) in (st, "rig")]
        else:
            frame_objs = subject
        long_side = r["preview_long_side_px"] if preview else (r["hero_long_side_px"] if v.get("hero") else r["long_side_px"])
        self.place_floor(frame_objs)
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
    argv = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else sys.argv[1:]
    if len(argv) < 2:
        raise SystemExit("usage: render.py JOB.json OUTDIR [--views a,b] [--preview]")
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
