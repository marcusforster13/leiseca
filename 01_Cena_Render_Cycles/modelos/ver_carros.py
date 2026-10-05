"""Renderiza uma folha de conferencia dos carros extraidos (frente = +X, seta vermelha).  blender -b --factory-startup --python ver_carros.py -- hatch suv van guincho"""
import bpy, os, sys, math
from mathutils import Vector
AQUI = os.path.dirname(os.path.abspath(__file__))
nomes = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else ["hatch"]
bpy.ops.wm.read_factory_settings(use_empty=True)
sc = bpy.context.scene
for i, n in enumerate(nomes):
    antes = set(bpy.data.objects)
    bpy.ops.import_scene.gltf(filepath=os.path.join(AQUI, "carros", n + ".glb"))
    raiz = next(o for o in bpy.data.objects if o not in antes and o.parent is None)
    raiz.location = (0, -i * 3.2, 0)
    bpy.ops.mesh.primitive_cone_add(radius1=.15, depth=.5, location=(4.6, -i * 3.2, .15), rotation=(0, math.pi / 2, 0))
    m = bpy.data.materials.new("seta"); m.diffuse_color = (1, 0, 0, 1)
    m.node_tree.nodes["Principled BSDF"].inputs["Base Color"].default_value = (1, 0, 0, 1); bpy.context.object.data.materials.append(m)
bpy.ops.mesh.primitive_plane_add(size=80)
w = bpy.data.worlds.new("w"); sc.world = w; w.node_tree.nodes["Background"].inputs["Strength"].default_value = 1.2
sun = bpy.data.lights.new("s", "SUN"); sun.energy = 3; so = bpy.data.objects.new("s", sun); sc.collection.objects.link(so); so.rotation_euler = (.8, 0, .6)
cam = bpy.data.cameras.new("c"); co = bpy.data.objects.new("c", cam); sc.collection.objects.link(co); sc.camera = co
alvo = Vector((0, -(len(nomes) - 1) * 1.6, .6)); co.location = alvo + Vector((9, 9 + len(nomes), 5.5))
co.rotation_euler = (alvo - co.location).to_track_quat("-Z", "Y").to_euler(); cam.lens = 35
sc.render.engine = "CYCLES"; sc.cycles.samples = 32; sc.cycles.use_denoising = True
sc.render.resolution_x, sc.render.resolution_y = 1280, 800
sc.render.image_settings.file_format = "JPEG"
sc.render.filepath = os.path.normpath(os.path.join(AQUI, "..", "..", ".claude", "capturas", "carros.jpg"))
bpy.ops.render.render(write_still=True)
