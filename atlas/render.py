"""Render the atlas views with Blender, headless.

Look: every mechanism part gets a finish from scene.yaml's palette through the
registry (read off photographs of the real parts), a three-light studio with a
matte floor, AgX tone mapping; isolation views draw the subject in its finish
with a dark outline over unlit grey silhouettes of the rest (Freestyle).

    blender -b --python atlas/render.py -- atlas/job.json docs/renders/ [--views a,b] [--preview] [--model PATH] [--no-views]
    python atlas/render.py atlas/job.json docs/renders/ [--views a,b] [--preview] [--model PATH] [--no-views]   # with the bpy wheel

`--model PATH` also exports the assembled model with these finishes as a
GLB for the site's <model-viewer> (`--no-views` exports it alone).

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
        self.looks = {}
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
        self.board_of = {}           # board mesh -> board id, for `subject: boards:<id>`
        self.always_hidden = set()   # hidden at load (dropped faces); restore() keeps them so
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
                    self.board_objs.append(o); self.board_of[o] = bid
                self.fix_board(bid, e, tops, inst["station"])
                log(f"board {bid} at {inst['station']}: {len(tops)} top nodes, size {[round(v, 3) for v in (mx - mn)]}")
        bpy.context.view_layer.update()
        self.all_objs = [o for o in bpy.data.objects if o.type == "MESH"]
        # Local matrices, not world ones: restoring matrix_world object by
        # object goes through each parent's *current* world matrix, so the
        # children of an exploded part came back displaced by the explode
        # offset (the brake housing by 130 mm) in every view after an
        # exploded one. matrix_basis has no such dependency.
        self.orig_matrix = {o: o.matrix_basis.copy() for o in bpy.data.objects}
        self.apply_looks(job["render"])
        self.setup_render()
        self.setup_studio()
        self.setup_isolation()

    # ------------------------------------------------------------ materials

    def fix_board(self, bid, root, tops, station):
        """KiCad's export, made presentable: drop the silkscreen face, cap pure
        white bodies, and stand in for a connector that has no model.

        Frames: the glTF importer has already turned the board's Y-up frame
        into Blender's Z-up, so in the instance's local space the board lies in
        XY with Z its normal, and the drawings' frame (centre origin, X right,
        Y up, millimetres) maps onto it by translation and scale alone."""
        fx = self.job.get("board_fixes", {})
        meshes = meshes_under(tops)
        body = None
        for o in meshes:
            bb = [Vector(c) for c in o.bound_box]
            lo = Vector((min(v.x for v in bb), min(v.y for v in bb), min(v.z for v in bb)))
            hi = Vector((max(v.x for v in bb), max(v.y for v in bb), max(v.z for v in bb)))
            size = hi - lo
            if size.x > 0.09 and size.y > 0.05 and size.z > 0.001:
                body = (lo, hi)
            if fx.get("drop_silkscreen_faces") and size.x > 0.09 and size.y > 0.05 and size.z < 0.0005:
                mats = [sl.material for sl in o.material_slots if sl.material]
                if mats and all(self._is_white_ish(m) for m in mats):
                    o.hide_render = True
                    self.always_hidden.add(o)
                    self.board_objs.remove(o)
                    self.station_of.pop(o, None)
                    log(f"board {bid}: dropped the silkscreen face {o.name}")
        # KiCad's exported materials, matched by base colour (and by alpha when
        # the match has four values): the translucent solder mask, the
        # silkscreen and the FR4 body become opaque looks from the palette. A
        # mesh with no material at all (a STEP model exported without colour:
        # the RJ-45 and the BNC jacks) gets `missing_material_look`. Whatever
        # is left is made opaque, and pure whites are capped.
        rules = fx.get("material_looks", []); tol = fx.get("match_tolerance", 0.02)
        cap = fx.get("white_cap"); n_rule = n_missing = 0
        for o in meshes:
            if not any(sl.material for sl in o.material_slots):
                look = fx.get("missing_material_look")
                if look:
                    o.data.materials.clear(); o.data.materials.append(self.look_material(look)); n_missing += 1
                continue
            for sl in o.material_slots:
                m = sl.material
                if not (m and m.use_nodes) or m.name.startswith("look:"):
                    continue
                bsdf = next((n for n in m.node_tree.nodes if n.type == "BSDF_PRINCIPLED"), None)
                if bsdf is None:
                    continue
                c = bsdf.inputs["Base Color"].default_value
                a = 1.0 if bsdf.inputs["Alpha"].is_linked else bsdf.inputs["Alpha"].default_value
                hit = None
                for rule in rules:
                    want = rule["match"]
                    if all(abs(c[i] - want[i]) <= tol for i in range(3)) and (len(want) < 4 or abs(a - want[3]) <= tol):
                        hit = rule["look"]; break
                if hit:
                    sl.material = self.look_material(hit); n_rule += 1
                    continue
                if cap and min(c[0], c[1], c[2]) > 0.95:
                    bsdf.inputs["Base Color"].default_value = (cap, cap, cap, 1)
                if not bsdf.inputs["Alpha"].is_linked:
                    bsdf.inputs["Alpha"].default_value = 1.0
                m.surface_render_method = "DITHERED"
        log(f"board {bid}: {n_rule} material slots relabelled by colour, {n_missing} meshes without a material given {fx.get('missing_material_look')}")
        if body is None:
            log(f"board {bid}: no body mesh found, no proxies"); return
        lo, hi = body
        centre = Vector(((lo.x + hi.x) / 2, (lo.y + hi.y) / 2, hi.z))  # top face centre
        for px in fx.get("proxies", {}).get(bid, []):
            at = centre + Vector((px["x_mm"] / 1000, px["y_mm"] / 1000, 0))
            objs = []
            if px.get("mesh"):
                before = set(bpy.data.objects)
                # KiCad's model frame is X right, Y up the board, Z the normal: Blender's, so no axis swap
                bpy.ops.wm.obj_import(filepath=os.path.join(self.root, px["mesh"]), forward_axis="Y", up_axis="Z", global_scale=0.001, use_split_objects=True, use_split_groups=True)
                objs = [o for o in bpy.data.objects if o not in before and o.type == "MESH"]
                holder = bpy.data.objects.new(f"proxy:{px['name']}", None)
                bpy.context.scene.collection.objects.link(holder)
                for o in objs:
                    o.parent = holder
                    look = px.get("look", "black-plastic")
                    for pat, lk in (px.get("looks_by_name") or {}).items():
                        if fnmatch.fnmatchcase(base(o.name), pat):
                            look = lk
                    o.data.materials.clear(); o.data.materials.append(self.look_material(look))
                holder.parent = root
                holder.location = at
                holder.rotation_euler = (0, 0, math.radians(px.get("rotation_deg", 0)))
                shapes = [o for o in objs]
            else:
                w, h, ht = px["w_mm"] / 1000, px["h_mm"] / 1000, px["height_mm"] / 1000
                me = bpy.data.meshes.new(f"proxy:{px['name']}")
                vs = [(at.x + sx * w / 2, at.y + sy * h / 2, at.z + sz * ht) for sz in (0, 1) for sy in (-1, 1) for sx in (-1, 1)]
                fs = [(0, 1, 3, 2), (4, 6, 7, 5), (0, 4, 5, 1), (2, 3, 7, 6), (0, 2, 6, 4), (1, 5, 7, 3)]
                me.from_pydata(vs, [], fs)
                pr = bpy.data.objects.new(f"proxy:{px['name']}", me)
                bpy.context.scene.collection.objects.link(pr)
                pr.parent = root
                me.materials.append(self.look_material(px.get("look", "black-plastic")))
                shapes = [pr]
            for o in shapes:
                self.station_of[o] = station; self.board_objs.append(o); self.board_of[o] = bid
            log(f"board {bid}: stand-in for {px['name']} ({'mesh' if px.get('mesh') else 'box'}, {len(shapes)} objects)")

    @staticmethod
    def _is_white_ish(m):
        if not m.use_nodes:
            return False
        for node in m.node_tree.nodes:
            if node.type == "BSDF_PRINCIPLED":
                c = node.inputs["Base Color"].default_value
                return min(c[0], c[1], c[2]) > 0.9
        return False

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
        if "coat" in spec:
            bsdf.inputs["Coat Weight"].default_value = spec["coat"]
            bsdf.inputs["Coat Roughness"].default_value = spec.get("coat_roughness", 0.1)
        if "specular" in spec:
            bsdf.inputs["Specular IOR Level"].default_value = spec["specular"]
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
        # the boards: KiCad's materials (those fix_board left), with only the mirror finishes tamed
        for o in self.board_objs:
            for slot in o.material_slots:
                m = slot.material
                if m and m.use_nodes and not m.name.startswith("look:"):
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
        # the ghost: the same flat grey, mostly transparent, for context parts
        # that stand between the camera and the subject
        self.ghost_mat = bpy.data.materials.new("atlas_ghost"); self.ghost_mat.use_nodes = True
        nt = self.ghost_mat.node_tree
        for node in list(nt.nodes):
            if node.type != "OUTPUT_MATERIAL":
                nt.nodes.remove(node)
        em = nt.nodes.new("ShaderNodeEmission"); em.inputs["Color"].default_value = (c[0], c[1], c[2], 1)
        tr = nt.nodes.new("ShaderNodeBsdfTransparent")
        mix = nt.nodes.new("ShaderNodeMixShader")
        mix.inputs["Fac"].default_value = r.get("isolate", {}).get("ghost_opacity", 0.22)
        nt.links.new(tr.outputs[0], mix.inputs[1]); nt.links.new(em.outputs[0], mix.inputs[2])
        nt.links.new(mix.outputs[0], nt.nodes["Material Output"].inputs["Surface"])
        self.ghost_mat.surface_render_method = "BLENDED"

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
        if f.get("shadow_catcher") and scn.render.film_transparent:
            self.floor.is_shadow_catcher = True
            log("floor: shadow catcher")
        log(f"studio: R={R:.3f} m, {len(self.lights)} lights, floor {size:.1f} m")

    def setup_isolation(self):
        """Collections Freestyle selects by, and the two line sets."""
        scn = bpy.context.scene; r = self.job["render"].get("isolate", {})
        self.coll_subject = bpy.data.collections.new("atlas_subject"); scn.collection.children.link(self.coll_subject)
        self.coll_context = bpy.data.collections.new("atlas_context"); scn.collection.children.link(self.coll_context)
        self.coll_ghost = bpy.data.collections.new("atlas_ghost"); scn.collection.children.link(self.coll_ghost)
        scn.render.line_thickness_mode = "ABSOLUTE"
        fs = bpy.context.view_layer.freestyle_settings
        fs.crease_angle = math.radians(r.get("crease_angle_deg", 110))
        fs.use_culling = True
        for ls in list(fs.linesets):
            fs.linesets.remove(ls)
        for name, coll, spec in (("subject", self.coll_subject, r.get("subject_line", {})), ("context", self.coll_context, r.get("context_line", {})),
                                 ("ghost", self.coll_ghost, r.get("ghost_line", r.get("context_line", {})))):
            ls = fs.linesets.new(name)
            ls.select_by_collection = True; ls.collection = coll; ls.collection_negation = "INCLUSIVE"
            ls.select_silhouette = True; ls.select_border = True; ls.select_crease = True
            ls.select_edge_mark = False; ls.select_contour = False; ls.select_external_contour = False
            c = spec.get("color", [0.1, 0.1, 0.1])
            ls.linestyle.color = (c[0], c[1], c[2]); ls.linestyle.thickness = spec.get("thickness", 1.0)
            ls.linestyle.alpha = 1.0
        scn.render.use_freestyle = False

    def set_isolation(self, on, subject, visible):
        """Subject in its looks, the rest a flat grey; and the context parts
        that stand between the camera and the subject become ghosts, so the
        subject is seen rather than covered. Needs the camera placed."""
        scn = bpy.context.scene
        for coll in (self.coll_subject, self.coll_context, self.coll_ghost):
            for o in list(coll.objects):
                coll.objects.unlink(o)
        scn.render.use_freestyle = bool(on)
        if not on:
            return
        subj = set(subject)
        occluders, blocked = self.occluders(subject, visible)
        for o in visible:
            (self.coll_subject if o in subj else self.coll_ghost if o in occluders else self.coll_context).objects.link(o)
            if o not in subj:
                mat = self.ghost_mat if o in occluders else self.context_mat
                for sl in o.material_slots:
                    sl.material = mat
                if not o.material_slots:
                    o.data.materials.append(mat)
        log(f"isolation: {len(occluders)} context objects in front of the subject ghosted ({blocked:.0%} of the sample rays were blocked)")

    def occluders(self, subject, visible):
        """Context objects hit by rays from the camera to sample points on the
        subject before the rays reach it. Hidden objects and the floor are
        passed through."""
        r = self.job["render"].get("isolate", {})
        scn = bpy.context.scene
        bpy.context.view_layer.update()
        dg = bpy.context.evaluated_depsgraph_get()
        subj = set(subject); vis = set(visible)
        pts = []
        for o in subject:
            if o.type != "MESH":
                continue
            vs = o.data.vertices; n = len(vs)
            step = max(1, n // max(1, r.get("sample_rays", 400) // max(1, len(subject))))
            pts += [o.matrix_world @ vs[i].co for i in range(0, n, step)]
            pts += [o.matrix_world @ Vector(c) for c in o.bound_box]
        cam = self.cam.matrix_world.translation
        hits = {}; blocked = 0
        for p in pts:
            d = p - cam; dist = d.length; d.normalize()
            origin = cam.copy(); travelled = 0.0; seen = set()
            for _ in range(24):
                ok, loc, _, _, obj, _ = scn.ray_cast(dg, origin, d, distance=dist - travelled - 1e-5)
                if not ok or obj is None:
                    break
                obj = obj.original if hasattr(obj, "original") else obj
                if obj in subj:
                    break
                if obj in vis and obj not in seen:
                    seen.add(obj)
                step = (loc - origin).length + 1e-4
                origin = origin + d * step; travelled += step
            if seen:
                blocked += 1
                for o in seen:
                    hits[o] = hits.get(o, 0) + 1
        min_hits = max(1, int(r.get("ghost_min_fraction", 0.01) * len(pts)))
        return {o for o, n in hits.items() if n >= min_hits}, (blocked / len(pts) if pts else 0.0)

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
        if spec == "boards":
            return list(self.board_objs)
        if kind == "boards":
            return [o for o in self.board_objs if self.board_of.get(o) == arg]
        if kind == "entry":
            tops = [t for t in self.entry_objs[entry] if arg in ("any", self.station_of.get(t)) or self.station_of.get(t) == "rig"]
            return meshes_under(tops)
        raise SystemExit(f"unknown subject {spec}")

    def restore(self):
        for o, mats in self.orig_mats.items():
            for s, m in zip(o.material_slots, mats):
                s.material = m
        for o, m in self.orig_matrix.items():
            o.matrix_basis = m
        for o in bpy.data.objects:
            o.hide_render = o in self.always_hidden
        bpy.context.view_layer.update()

    def explode(self, factor, station):
        """Exploded view by clearance, not by a fixed step. Every entry with an
        `explode` field moves along its axis in the direction given by the sign
        of `order` (axis z: positive away from the lever; axis y: positive
        down), in order of |order|. Each group (the entries sharing one order)
        moves just far enough that its bounding box clears, by `gap`, every
        box already placed that it overlaps in the other two axes: the
        station's fixed meshes, the entries of other chains, and the groups
        before it in its own chain. `factor` scales the whole spread, so the
        100 % view has no intersecting boxes and the partial views are
        proportionally tighter. Lever-axis chains are placed first, so the
        parts they move are out of the way of the downward stack. Entries
        with `explode: {ignore: true}` stay in place and constrain nothing
        (the frame standoffs the parts slide along); entries with
        `explode: {hide: true}` are hidden by render_view before this runs."""
        gap = self.job["explode"].get("gap", 0.02)
        zs = self.job["stations"][station]["z_sign"]

        def gbox(objs):
            mn, mx = world_aabb(objs)
            if mn.x > mx.x:
                return None
            a, b = G_inv(mn), G_inv(mx)
            return [min(a[i], b[i]) for i in range(3)], [max(a[i], b[i]) for i in range(3)]

        def shifted(b, ax, d):
            lo, hi = [list(b[0]), list(b[1])]; lo[ax] += d; hi[ax] += d
            return lo, hi

        def crosses(b, p, ax):
            return all(min(b[1][i], p[1][i]) - max(b[0][i], p[0][i]) > 1e-4 for i in range(3) if i != ax)

        def tops_of(eid):
            return [t for t in self.entry_objs[eid] if self.station_of.get(t) in (station, "rig")]

        chains = {}   # (axis, sign) -> {|order|: [entry id]}
        for e in self.job["entries"]:
            x = e.get("explode")
            if not x or not x.get("order") or e["id"] not in self.entry_objs or not tops_of(e["id"]):
                continue
            chains.setdefault((x["axis"], 1 if x["order"] > 0 else -1), {}).setdefault(abs(x["order"]), []).append(e["id"])
        moving = {eid for ch in chains.values() for ids in ch.values() for eid in ids}
        orig = {eid: gbox(meshes_under(tops_of(eid))) for eid in moving}
        moving_meshes = {o for eid in moving for o in meshes_under(tops_of(eid))}
        ignored = {o for e in self.job["entries"] if (e.get("explode") or {}).get("ignore") and e["id"] in self.entry_objs
                   for o in meshes_under(self.entry_objs[e["id"]])}
        fixed = [b for b in (gbox([o]) for o in self.all_objs
                             if o not in moving_meshes and o not in ignored and o not in self.board_objs and not o.hide_render
                             and self.station_of.get(o) in (station, "rig")) if b]
        final = {}    # entry id -> its box at full spread
        offsets = {}  # entry id -> (axis index, signed metres at full spread)
        for (axis, sign), chain in sorted(chains.items(), key=lambda kv: (kv[0][0] != "z", kv[0][1])):
            ax = 2 if axis == "z" else 1
            direction = zs * sign if axis == "z" else -sign
            placed = fixed + [final.get(eid) or orig[eid] for eid in moving if eid not in {i for ids in chain.values() for i in ids}]
            need = 0.0
            for k in sorted(chain):
                for eid in chain[k]:
                    b = orig[eid]
                    for p in placed:
                        if crosses(b, p, ax):
                            d = (p[1][ax] - b[0][ax]) if direction > 0 else (b[1][ax] - p[0][ax])
                            need = max(need, d + gap)
                for eid in chain[k]:
                    final[eid] = shifted(orig[eid], ax, direction * need)
                    offsets[eid] = (ax, direction * need)
                    placed.append(final[eid])
        for eid, (ax, d) in offsets.items():
            v = [0.0, 0.0, 0.0]; v[ax] = d * factor
            for t in tops_of(eid):
                t.matrix_world = Matrix.Translation(G(v)) @ t.matrix_world
        bpy.context.view_layer.update()
        spread = {eid: round(d * factor * 1000) for eid, (ax, d) in offsets.items()}
        log(f"explode {factor}: offsets in mm {spread}")

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

    def export_model(self, path, boards=False):
        """The assembled model with the atlas finishes, for the site's
        <model-viewer>: every mechanism mesh at rest in its look, the boards
        only if asked, no lights, camera or floor. The source glTF carries
        Inventor's appearance names and nothing else, so the viewer showed
        white gears and a blue plate while the renders had the photographed
        finishes. Blender's exporter writes Y up, so the file is in the
        source model's frame and the hotspot centres apply unchanged."""
        self.restore()
        objs = [o for o in self.all_objs if not o.hide_render and o is not self.floor
                and (boards or o not in self.board_objs)]
        for o in bpy.context.view_layer.objects:
            o.select_set(False)
        for o in objs:
            o.select_set(True)
        os.makedirs(os.path.dirname(os.path.abspath(path)), exist_ok=True)
        bpy.ops.export_scene.gltf(filepath=path, export_format="GLB", use_selection=True,
                                  export_apply=True, export_yup=True, export_materials="EXPORT",
                                  export_lights=False, export_cameras=False, export_animations=False,
                                  export_skins=False, export_morph=False, export_extras=False)
        n_mat = len({s.material for o in objs for s in o.material_slots if s.material})
        log(f"model: {len(objs)} meshes, {n_mat} materials -> {path} ({os.path.getsize(path) / 1e6:.1f} MB)")

    def render_view(self, v, outdir, preview):
        r = self.job["render"]
        self.restore()
        entry = v.get("entry")
        hidden = set()
        boards = v.get("boards")       # true: every board; a board id or a list of them: only those
        if not boards:
            hidden.update(self.board_objs)
        elif boards is not True:
            wanted = [boards] if isinstance(boards, str) else list(boards)
            hidden.update(o for o in self.board_objs if self.board_of.get(o) not in wanted)
        if v.get("hide"):
            _, _, arg = v["hide"].partition(":")
            hidden.update(o for o in self.all_objs if self.station_of.get(o) == arg)
        if v["subject"].startswith("station:"):
            st = v["subject"].split(":")[1]
            hidden.update(o for o in self.all_objs if self.station_of.get(o) not in (st, "rig"))
        if v.get("explode"):
            # hardware the exploded views omit (registry `explode: {hide: true}`)
            for e in self.job["entries"]:
                if (e.get("explode") or {}).get("hide") and e["id"] in self.entry_objs:
                    hidden.update(meshes_under(self.entry_objs[e["id"]]))
        for o in hidden:
            o.hide_render = True
        visible = [o for o in self.all_objs if o not in hidden]
        subject = [o for o in self.objs_of(v["subject"], entry) if o not in hidden]
        subj = set(subject)
        if v.get("explode"):
            st = v["subject"].split(":")[1] if ":" in v["subject"] else "right"
            self.explode(v["explode"], st)
            frame_objs = [o for o in visible if self.station_of.get(o) in (st, "rig")]
        else:
            frame_objs = subject
        long_side = r["preview_long_side_px"] if preview else (r["hero_long_side_px"] if v.get("hero") else r["long_side_px"])
        self.place_floor(visible)   # the catcher hides what lies below it: never under the subject alone
        self.frame(frame_objs, v["camera"], long_side)
        self.set_isolation(v.get("others") == "isolate", subject, visible)   # after frame(): it casts rays from the camera
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
        raise SystemExit("usage: render.py JOB.json OUTDIR [--views a,b] [--preview] [--model PATH] [--no-views]")
    job_path, outdir = argv[0], argv[1]
    only = None; preview = False; model = None; no_views = False; i = 2
    while i < len(argv):
        if argv[i] == "--views":
            only = argv[i + 1].split(","); i += 2
        elif argv[i] == "--preview":
            preview = True; i += 1
        elif argv[i] == "--model":
            model = argv[i + 1]; i += 2
        elif argv[i] == "--no-views":
            no_views = True; i += 1
        else:
            raise SystemExit(f"unknown argument {argv[i]}")
    job = json.load(open(job_path))
    os.makedirs(outdir, exist_ok=True)
    bpy.ops.wm.read_factory_settings(use_empty=True)
    scene = Scene(job, job["root"])
    views = [] if no_views else [v for v in job["views"] if only is None or v["id"] in only]
    log(f"{len(views)} views, preview={preview}" + (f", model -> {model}" if model else ""))
    for v in views:
        scene.render_view(v, outdir, preview)
    if model:
        scene.export_model(model)
    if not preview and (views or model):
        # The manifest says which inputs the renders came from. A full render
        # (every view, and the model when asked) writes it afresh; a `--views`
        # render or a model export alone into the same directory updates the
        # inputs and records what was made alone, so `build.py --check` can
        # say that the other renders predate the current inputs.
        path = os.path.join(outdir, "manifest.json")
        man = {"inputs": job.get("inputs", {}), "views": [v["id"] for v in job["views"]], "blender": bpy.app.version_string}
        if model:
            man["model"] = model
        if only is not None or no_views:
            old = json.load(open(path)) if os.path.exists(path) else {}
            partial = set(old.get("partial_renders", [])) | {v["id"] for v in views} | ({"model"} if model else set())
            man["partial_renders"] = sorted(partial)
            man.setdefault("model", old.get("model"))
            log(f"manifest: inputs updated after making {', '.join(sorted(partial))} alone")
        with open(path, "w") as f:
            json.dump(man, f, indent=1)
    log("done")


if __name__ == "__main__":
    main()
