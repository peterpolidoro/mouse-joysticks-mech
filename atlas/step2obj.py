"""Tessellate a STEP model to OBJ, one group per solid, with FreeCAD.

    FreeCADCmd atlas/step2obj.py <model.step> <out.obj>      # e.g. through `guix shell freecad`

Used for the FFC socket (atlas/boards/FH12-50S-0.5SVA-54.obj) from kicad-libs'
3dmodels/orb_weaver.3dshapes/mechanical/FH12-50S-0.5SVA-54.step: the boards'
placed footprints still point at an older model file, so their exports lack
the part, and render.py stands this mesh in at the footprint's position
(scene.yaml, board_fixes.proxies). The OBJ keeps KiCad's model frame
(millimetres; X right, Y up the board, Z the board normal) and the STEP's
solid labels as group names, which the looks are assigned by.
"""
import os, sys
import FreeCAD, Import, Mesh, MeshPart

args = [a for a in sys.argv if a.endswith(".step") or a.endswith(".obj")]
step, out = args[0], args[1]
doc = FreeCAD.newDocument("model")
Import.insert(step, doc.Name)
leaves = [o for o in doc.Objects if hasattr(o, "Shape") and o.Shape.Solids and not [c for c in o.OutList if hasattr(c, "Shape")]]
feats = []
for o in leaves:
    m = MeshPart.meshFromShape(Shape=o.Shape, LinearDeflection=0.02, AngularDeflection=0.3, Relative=False)
    f = doc.addObject("Mesh::Feature", "M_" + o.Label)
    f.Mesh = m; f.Label = o.Label
    feats.append(f)
Mesh.export(feats, out)
print(f"{out}: {len(feats)} solids, {sum(f.Mesh.CountFacets for f in feats)} facets, {os.path.getsize(out)} bytes")
