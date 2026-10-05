"""Renderiza previas da cena (Cycles, rapido) em ../.claude/capturas.  Uso: blender -b blitz_lei_seca.blend --python renderizar_previa.py -- Camera_Aerea Camera_Abordagem"""
import bpy, os, sys
args = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else ["Camera_Aerea"]
sc = bpy.context.scene
out = os.path.normpath(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", ".claude", "capturas"))
sc.render.resolution_x, sc.render.resolution_y = 1280, 720
sc.cycles.samples = 48; sc.cycles.use_denoising = True
sc.render.image_settings.file_format = "JPEG"; sc.render.image_settings.quality = 85
for nome in args:
    sc.camera = bpy.data.objects[nome]
    sc.render.filepath = os.path.join(out, "previa_" + nome + ".jpg")
    bpy.ops.render.render(write_still=True)
    print("[PREVIA] " + sc.render.filepath)
