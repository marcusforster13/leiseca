"""
Operacao Lei Seca - separa os carros dos pacotes baixados do Sketchfab em um .glb por veiculo.

Fonte (licenca CC-BY 4.0, autor Comrade1280 - ver CREDITOS.md):
  _fontes/passageiros/scene.gltf   "Generic passenger car pack"
  _fontes/servicos/scene.gltf      "Generic civil service vehicles pack"
Saida: carros/<nome>.glb  - frente para +X, rodas no chao (z = 0), centro no meio do carro, em metros.
  Estrutura: raiz vazia <nome> > Carroceria (malhas do corpo) + Roda_DE, Roda_DD, Roda_TE, Roda_TD (giram no eixo Y local)
  Nos veiculos de servico as rodas vem coladas na carroceria: o script recorta pelas posicoes dos eixos quando indicado.

Uso:  blender -b --factory-startup --python extrair_carros.py            (extrai)
      blender -b --factory-startup --python extrair_carros.py -- info    (so lista o que ha nos pacotes)
"""
import bpy, os, sys, math
from mathutils import Vector, Matrix

AQUI = os.path.dirname(os.path.abspath(__file__))
INFO = "info" in sys.argv
SAIDA = os.path.join(AQUI, "carros"); os.makedirs(SAIDA, exist_ok=True)

def say(m): print("[CARROS] " + m)

# nome de saida -> (pacote, no do corpo, giro extra em graus para a frente ficar em +X)
VEICULOS = {
    "hatch":   ("passageiros", "Hatchback Body", 90),
    "compacto": ("passageiros", "Compact Body", 90),
    "seda":    ("passageiros", "Sedan Body", 90),
    "perua":   ("passageiros", "Wagon Body", 90),
    "suv":     ("passageiros", "SUV Body", 90),
    "minivan": ("passageiros", "minivan body", 90),
    "guincho": ("servicos", "towtruck", 90),
    "van":     ("servicos", "postvan", 90),
    "taxi":    ("servicos", "taxi", 90),
    "onibus":  ("servicos", "citybus", 90),
}

def limpar():
    bpy.ops.wm.read_factory_settings(use_empty=True)

def caixa_mundo(objs):
    pts = [o.matrix_world @ Vector(c) for o in objs for c in o.bound_box]
    mn = Vector((min(p.x for p in pts), min(p.y for p in pts), min(p.z for p in pts)))
    mx = Vector((max(p.x for p in pts), max(p.y for p in pts), max(p.z for p in pts)))
    return mn, mx

def malhas(o):
    return [c for c in [o] + list(o.children_recursive) if c.type == "MESH"]

def importar(pacote):
    limpar()
    bpy.ops.import_scene.gltf(filepath=os.path.join(AQUI, "_fontes", pacote, "scene.gltf"))
    bpy.context.view_layer.update()

if INFO:
    for pacote in ("passageiros", "servicos"):
        importar(pacote)
        say("===== " + pacote)
        raiz = next(o for o in bpy.data.objects if o.name.startswith("RootNode"))
        for o in raiz.children:
            ms = malhas(o)
            if not ms: continue
            mn, mx = caixa_mundo(ms); d = mx - mn; c = (mn + mx) / 2
            say("%-18s centro (%6.2f %6.2f %5.2f)  tam (%5.2f %5.2f %5.2f)  rotZ %6.1f  tris %d" % (
                o.name, c.x, c.y, c.z, d.x, d.y, d.z, math.degrees(o.matrix_world.to_euler().z),
                sum(len(m.data.polygons) for m in ms)))
    raise SystemExit

feitos = []
for nome, (pacote, corpo_nome, giro) in VEICULOS.items():
    importar(pacote)
    raiz = next(o for o in bpy.data.objects if o.name.startswith("RootNode"))
    corpo = next((o for o in raiz.children if o.name == corpo_nome), None)
    if not corpo:
        say("AVISO: %s nao encontrado em %s" % (corpo_nome, pacote)); continue
    mn, mx = caixa_mundo(malhas(corpo)); centro = (mn + mx) / 2
    # rodas: nos irmaos "Wheel_*" dentro da caixa do corpo (com folga)
    rodas = []
    for o in raiz.children:
        if o is corpo or not o.name.startswith("Wheel"): continue
        ms = malhas(o)
        if not ms: continue
        a, b = caixa_mundo(ms); c = (a + b) / 2
        dz = (o.matrix_world.to_euler().z - corpo.matrix_world.to_euler().z) % (2 * math.pi)
        if mn.x - .3 < c.x < mx.x + .3 and mn.y - .3 < c.y < mx.y + .3 and min(dz, 2 * math.pi - dz) < .05: rodas.append(o)
    manter = set([corpo] + list(corpo.children_recursive))
    for r in rodas: manter |= set([r] + list(r.children_recursive))
    ms_corpo = malhas(corpo); ms_rodas = [malhas(r) for r in rodas]
    for o in list(bpy.data.objects):
        if o not in manter: bpy.data.objects.remove(o, do_unlink=True)
    # solta tudo no mundo, gira para a frente ficar em +X e centraliza
    for o in list(manter):
        mw = o.matrix_world.copy(); o.parent = None; o.matrix_world = mw
    bpy.context.view_layer.update()
    rz = -corpo.matrix_world.to_euler().z + math.radians(giro)
    z0 = min([mn.z] + [caixa_mundo(ms)[0].z for ms in ms_rodas])          # o chao e a base dos pneus, nao da carroceria
    T = Matrix.Rotation(rz, 4, "Z") @ Matrix.Translation((-centro.x, -centro.y, -z0))
    R = bpy.data.objects.new(nome, None); bpy.context.scene.collection.objects.link(R)
    def juntar(ms, novo_nome, origem=None):
        for m in ms: m.matrix_world = T @ m.matrix_world
        bpy.context.view_layer.update()
        alvo = ms[0]
        if len(ms) > 1:
            with bpy.context.temp_override(active_object=alvo, selected_objects=ms, selected_editable_objects=ms):
                bpy.ops.object.join()
        with bpy.context.temp_override(active_object=alvo, selected_objects=[alvo], selected_editable_objects=[alvo]):
            bpy.ops.object.transform_apply(location=True, rotation=True, scale=True)
        if origem == "centro":                                # origem no eixo da roda, para girar
            vs = [v.co for v in alvo.data.vertices]              # centro pelos vertices (a caixa do objeto ainda nao foi atualizada)
            c = Vector((sum(v.x for v in vs), sum(v.y for v in vs), sum(v.z for v in vs))) / len(vs)
            alvo.data.transform(Matrix.Translation(-c)); alvo.location = c
        alvo.name = novo_nome; alvo.data.name = novo_nome; alvo.parent = R
        return alvo
    juntar(ms_corpo, "Carroceria")
    rs = []
    for r in ms_rodas:
        a, b = caixa_mundo(r); c = T @ ((a + b) / 2)
        rs.append((c, r))
    for c, r in rs:
        juntar(r, "Roda_%s%s" % ("D" if c.x > 0 else "T", "E" if c.y > 0 else "D"), "centro")
    for o in [o for o in bpy.data.objects if o.type == "EMPTY" and o is not R]:
        bpy.data.objects.remove(o, do_unlink=True)
    a, b = caixa_mundo([o for o in R.children])
    for o in bpy.data.objects: o.select_set(True)
    bpy.ops.export_scene.gltf(filepath=os.path.join(SAIDA, nome + ".glb"), export_format="GLB", use_selection=True,
                              export_image_format="JPEG", export_image_quality=88, export_animations=False)
    d = b - a
    say("%-8s %.2f x %.2f x %.2f m, %d rodas soltas, %d tris, %.1f MB" % (nome, d.x, d.y, d.z, len(rs),
        sum(len(o.data.polygons) for o in R.children), os.path.getsize(os.path.join(SAIDA, nome + ".glb")) / 1048576))
    feitos.append(nome)
say("extraidos: " + ", ".join(feitos))
