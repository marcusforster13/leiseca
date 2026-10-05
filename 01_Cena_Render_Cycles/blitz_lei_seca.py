"""
Operacao Lei Seca - cena base para Blender 5.x (gera blitz_lei_seca.blend do zero)

Trecho de avenida do Rio de Janeiro, a noite, com a blitz montada: balao, tenda, van de apoio,
viatura da PM, guincho, cones, barreiras, cavaletes, torres de iluminacao, mesa de equipamentos,
carro abordado (com a janela do motorista aberta) e carro na area de regularizacao.

Uso:  blender -b --factory-startup --python blitz_lei_seca.py
Unidades em metros. X = ao longo da via (o transito segue para +X), Y = atravessa a via, Z = para cima.
Sem logotipos de marcas e sem brasoes oficiais: ha um espaco "Brasao_(inserir_imagem_oficial)".
"""
import bpy, bmesh, math, random, os
import numpy as np
from mathutils import Vector, Matrix

PI = math.pi
rnd = random.Random(2026)
try:
    AQUI = os.path.dirname(os.path.abspath(__file__))
except NameError:
    AQUI = os.path.join(os.path.expanduser("~"), "Downloads", "leiseca", "01_Cena_Render_Cycles")

def say(m): print("[BLITZ] " + m)

# ------------------------------------------------------------------ limpeza
for ob in list(bpy.data.objects):
    bpy.data.objects.remove(ob, do_unlink=True)
for c in list(bpy.data.collections):
    bpy.data.collections.remove(c)
scene = bpy.context.scene

def collection(name):
    c = bpy.data.collections.new(name); scene.collection.children.link(c); return c

C_RUA = collection("01_Rua")
C_PRED = collection("02_Predios")
C_VEG = collection("03_Arvores_Postes")
C_BLITZ = collection("04_Blitz_Estrutura")
C_SINAL = collection("05_Cones_Barreiras")
C_VEIC = collection("06_Veiculos_Apoio")
C_REG = collection("07_Carro_Regularizacao")
C_INT = collection("08_Interativos")
C_LUZ = collection("09_Luzes_Cameras")
C_ABORD = collection("10_Carro_Abordado")

# ------------------------------------------------------------------ materiais
def hx(h): return tuple(int(h[i:i + 2], 16) / 255 for i in (1, 3, 5))
def lin(c): return tuple(x / 12.92 if x <= .04045 else ((x + .055) / 1.055) ** 2.4 for x in c)

def mat(name, color, rough=.8, metal=0., emit=None, forca=0., alpha=None):
    m = bpy.data.materials.new(name)
    b = m.node_tree.nodes.get("Principled BSDF")
    c = lin(hx(color))
    b.inputs["Base Color"].default_value = (*c, 1)
    b.inputs["Roughness"].default_value = rough
    b.inputs["Metallic"].default_value = metal
    if emit:
        b.inputs["Emission Color"].default_value = (*lin(hx(emit)), 1)
        b.inputs["Emission Strength"].default_value = forca
    if alpha is not None:
        b.inputs["Alpha"].default_value = alpha
        for attr, val in (("surface_render_method", "BLENDED"), ("blend_method", "BLEND")):
            try: setattr(m, attr, val)
            except Exception: pass
    m.diffuse_color = (*c, 1 if alpha is None else alpha)
    return m

def np_image(name, arr):
    h, w, _ = arr.shape
    rgba = np.ones((h, w, 4), dtype=np.float32); rgba[..., :3] = arr
    img = bpy.data.images.new(name, w, h, alpha=False)
    img.pixels.foreach_set(np.flipud(rgba).ravel()); img.pack()
    return img

def img_mat(name, img, tile_m, rough=.6):
    """Textura gerada, projetada em caixa (coordenadas do objeto, em metros)."""
    m = bpy.data.materials.new(name); nt = m.node_tree; b = nt.nodes.get("Principled BSDF")
    tex = nt.nodes.new("ShaderNodeTexImage"); tex.image = img
    tc = nt.nodes.new("ShaderNodeTexCoord"); mp = nt.nodes.new("ShaderNodeMapping")
    mp.inputs["Scale"].default_value = (1 / tile_m,) * 3
    tex.projection = "BOX"; tex.projection_blend = .1
    nt.links.new(tc.outputs["Object"], mp.inputs["Vector"]); nt.links.new(mp.outputs["Vector"], tex.inputs["Vector"])
    nt.links.new(tex.outputs["Color"], b.inputs["Base Color"])
    b.inputs["Roughness"].default_value = rough
    m.diffuse_color = (.5, .5, .5, 1)
    return m

def tex_calcada(S=512):
    """Calcada de pedra portuguesa com ondas pretas e brancas (padrao tradicional carioca, desenho proprio)."""
    y, x = np.mgrid[0:S, 0:S] / S
    onda = np.sin((y + .12 * np.sin(x * 2 * PI)) * 2 * PI * 2)
    r = np.random.default_rng(5)
    branco, preto = np.array(hx("#d9d4c8")), np.array(hx("#2b2a28"))
    a = np.where((onda > 0)[..., None], branco, preto).astype(np.float64)
    cel = 16; g = r.uniform(.86, 1.06, (S // cel, S // cel, 1)); a *= np.kron(g, np.ones((cel, cel, 1)))
    yy, xx = np.mgrid[0:S, 0:S]
    a[(xx % cel == 0) | (yy % cel == 0)] *= .72            # juntas das pedrinhas
    return np.clip(a, 0, 1)

M = {
    "asfalto": mat("Asfalto", "#3a3a3c", .9),
    "faixa": mat("Pintura_Viaria_Branca", "#d8d6cc", .7),
    "faixa_am": mat("Pintura_Viaria_Amarela", "#d9a514", .7),
    "meiofio": mat("Meio_Fio_Concreto", "#9c988f", .95),
    "calcada": img_mat("Calcada_Portuguesa", np_image("calcada_portuguesa", tex_calcada()), 2.4, .75),
    "concreto": mat("Concreto_Aparente", "#a19d95", .95),
    "reboco_a": mat("Fachada_Areia", "#cdbf9f", .92), "reboco_b": mat("Fachada_Branca", "#dedad0", .92),
    "reboco_c": mat("Fachada_Terracota", "#a8684a", .92), "reboco_d": mat("Fachada_Cinza", "#8f9196", .92),
    "janela_on": mat("Janela_Acesa", "#3a3020", .4, emit="#ffc98a", forca=1.1),
    "janela_on2": mat("Janela_Acesa_Fria", "#20303a", .4, emit="#bcd8ff", forca=.8),
    "janela_off": mat("Janela_Apagada", "#10151c", .15),
    "loja": mat("Porta_Loja_Metal", "#5b5f66", .5, .6),
    "tronco": mat("Tronco_Arvore", "#5c4b3c", 1), "folha": mat("Folhagem", "#2c5230", .8),
    "terra": mat("Terra_Canteiro", "#4a3a2c", 1),
    "poste": mat("Poste_Metal", "#3b3d40", .5, .6),
    "lamp": mat("Luminaria_Publica", "#ffffff", .4, emit="#ffd9a0", forca=25),
    "led": mat("Refletor_LED", "#ffffff", .4, emit="#f4f7ff", forca=40),
    "tripe": mat("Tripe_Amarelo", "#d6a410", .45, .3),
    "preto": mat("Preto_Fosco", "#17181a", .6), "preto_b": mat("Preto_Brilhante", "#0c0c0d", .2),
    "branco": mat("Plastico_Branco", "#eceae4", .45),
    "azul": mat("Lona_Azul", "#1c3fa8", .6), "azul_claro": mat("Azul_Faixa", "#2a66d8", .5),
    "lona_balao": mat("Balao_Branco", "#f2f2ee", .5, emit="#ffffff", forca=1.6),
    "lona_balao_az": mat("Balao_Azul", "#1c3fa8", .5, emit="#2a55d0", forca=.9),
    "texto_az": mat("Texto_Azul", "#16307f", .6), "texto_br": mat("Texto_Branco", "#f4f4f0", .6),
    "texto_pr": mat("Texto_Preto", "#111111", .6),
    "cone": mat("Cone_Laranja", "#e8500e", .55), "refletivo": mat("Faixa_Refletiva", "#f1f1ec", .3),
    "metal": mat("Metal_Escovado", "#8a8c8e", .35, 1), "cromo": mat("Cromado", "#c9ccd0", .15, 1),
    "pneu": mat("Borracha_Pneu", "#141414", .9), "disco": mat("Disco_Freio", "#5a5c5e", .4, .8),
    "aro": mat("Roda_Liga", "#9a9da2", .32, .85), "aro_aco": mat("Roda_Aco", "#2a2b2d", .5, .6),
    "vidro": mat("Vidro_Carro_Fume", "#1a2228", .05, alpha=.35),
    "plast": mat("Plastico_Preto_Texturizado", "#1d1e20", .75),
    "interior": mat("Interior_Carro", "#2a2b2e", .8),
    "farol": mat("Farol_Aceso", "#ffffff", .2, emit="#fff4d8", forca=6),
    "lanterna": mat("Lanterna_Acesa", "#5a0a08", .3, emit="#ff1808", forca=3),
    "placa": mat("Placa_Mercosul", "#f2f2f2", .5), "placa_azul": mat("Placa_Faixa_Azul", "#1b3f9c", .5),
    "pint_pm": mat("Viatura_Pintura_Branca", "#e9eaec", .3), "faixa_pm": mat("Viatura_Faixa_Azul", "#1e4fb8", .3),
    "pint_van": mat("Van_Pintura_Branca", "#eceded", .3),
    "pint_cinza": mat("Carro_Pintura_Cinza", "#8d9096", .3, .15), "pint_branca": mat("Carro_Pintura_Branca", "#e6e6e4", .3),
    "pint_guincho": mat("Guincho_Pintura_Branca", "#e2e3e3", .35),
    "plataforma": mat("Guincho_Plataforma", "#4a4f55", .55, .7),
    "giro_verm": mat("Giroflex_Vermelho", "#5a0a08", .2, emit="#ff1010", forca=.05),
    "giro_azul": mat("Giroflex_Azul", "#08205a", .2, emit="#1040ff", forca=.05),
    "ambar": mat("Sinalizador_Ambar", "#7a4a05", .2, emit="#ffa010", forca=4),
    "brasao": mat("Brasao_(inserir_imagem_oficial)", "#c8cbd0", .5),
    "colete": mat("Colete_Refletivo", "#d7e21b", .6),
    "tela": mat("Tela_Acesa", "#000000", .2, emit="#9fc4ff", forca=2.5),
    "tela_verde": mat("Visor_Etilometro", "#000000", .2, emit="#8dffb0", forca=2.0),
    "maleta": mat("Maleta_Preta", "#1a1b1d", .55), "espuma": mat("Espuma_Maleta", "#2e3033", 1),
    "papel": mat("Papel", "#f6f3ea", .9), "bocal": mat("Bocal_Embalado", "#e8f0f4", .35),
    "barreira": mat("Barreira_Laranja", "#e2520f", .5),
}

# ------------------------------------------------------------------ geometria
def finish(name, bm, loc, mats, col, parent=None, rot=(0, 0, 0), smooth=False, bevel=0.0, seg=2):
    me = bpy.data.meshes.new(name); bm.to_mesh(me); bm.free()
    for p in me.polygons: p.use_smooth = smooth
    for m in (mats if isinstance(mats, (list, tuple)) else [mats]): me.materials.append(m)
    ob = bpy.data.objects.new(name, me); col.objects.link(ob)
    if parent: ob.parent = parent
    ob.location = loc; ob.rotation_euler = rot
    if bevel:
        b = ob.modifiers.new("Chanfro", "BEVEL"); b.width = bevel; b.segments = seg; b.limit_method = "ANGLE"
        for p in me.polygons: p.use_smooth = True
    return ob

def box(name, tam, pos, m, col, parent=None, rot=(0, 0, 0), bevel=0.0, seg=2):
    bm = bmesh.new(); bmesh.ops.create_cube(bm, size=1); bmesh.ops.scale(bm, vec=Vector(tam), verts=bm.verts)
    return finish(name, bm, pos, m, col, parent, rot, bevel=bevel, seg=seg)

def cyl(name, r1, r2, h, pos, m, col, parent=None, rot=(0, 0, 0), seg=20):
    bm = bmesh.new(); bmesh.ops.create_cone(bm, cap_ends=True, segments=seg, radius1=r1, radius2=r2, depth=h)
    return finish(name, bm, pos, m, col, parent, rot, smooth=True)

def barra(name, a, b, r, m, col, parent=None, seg=10):
    """Cilindro fino entre dois pontos."""
    a, b = Vector(a), Vector(b); d = b - a
    ob = cyl(name, r, r, d.length, (a + b) / 2, m, col, parent, seg=seg)
    ob.rotation_euler = Vector((0, 0, 1)).rotation_difference(d.normalized()).to_euler()
    return ob

def torno(name, perfil, mats, col, parent=None, pos=(0, 0, 0), rot=(0, 0, 0), seg=32, idx=None):
    """Solido de revolucao em torno de Z (perfil = [(raio, z), ...]); idx = material de cada segmento do perfil."""
    bm = bmesh.new(); aneis = []
    for k in range(seg):
        a = 2 * PI * k / seg
        aneis.append([bm.verts.new((r * math.cos(a), r * math.sin(a), z)) for r, z in perfil])
    for k in range(seg):
        A, B = aneis[k], aneis[(k + 1) % seg]
        for i in range(len(perfil) - 1):
            try:
                f = bm.faces.new((A[i], B[i], B[i + 1], A[i + 1]))
                if idx: f.material_index = idx[i]
            except ValueError: pass
    bmesh.ops.remove_doubles(bm, verts=bm.verts, dist=1e-5)
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
    return finish(name, bm, pos, mats, col, parent, rot, smooth=True)

def malha(name, verts, faces, m, col, parent=None, pos=(0, 0, 0), smooth=False, idx=None):
    me = bpy.data.meshes.new(name); me.from_pydata(verts, [], faces)
    bm = bmesh.new(); bm.from_mesh(me); bpy.data.meshes.remove(me)
    if idx:
        bm.faces.ensure_lookup_table()
        for f, i in zip(bm.faces, idx): f.material_index = i
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
    return finish(name, bm, pos, m, col, parent, smooth=smooth)

def texto_malha(conteudo, tam, espaco=1.0):
    cu = bpy.data.curves.new("_txt", "FONT"); cu.body = conteudo; cu.size = tam; cu.align_x = "CENTER"; cu.align_y = "CENTER"
    cu.resolution_u = 2; cu.space_character = espaco
    tmp = bpy.data.objects.new("_txt_tmp", cu); scene.collection.objects.link(tmp)
    bpy.context.view_layer.update()
    me = bpy.data.meshes.new_from_object(tmp.evaluated_get(bpy.context.evaluated_depsgraph_get()))
    bpy.data.objects.remove(tmp, do_unlink=True); bpy.data.curves.remove(cu)
    return me

# para onde o texto fica virado (quem le esta desse lado)
VIRADO = {"-y": (PI / 2, 0, 0), "+y": (PI / 2, 0, PI), "-x": (PI / 2, 0, -PI / 2), "+x": (PI / 2, 0, PI / 2), "cima": (0, 0, 0)}
def texto(name, conteudo, tam, pos, virado, m, col, parent=None, espaco=1.0):
    me = texto_malha(conteudo, tam, espaco); me.name = name; me.materials.append(m)
    ob = bpy.data.objects.new(name, me); col.objects.link(ob)
    if parent: ob.parent = parent
    ob.location = pos; ob.rotation_euler = VIRADO[virado] if isinstance(virado, str) else virado
    return ob

def vazio(name, pos, col, rz=0.0, parent=None):
    e = bpy.data.objects.new(name, None); col.objects.link(e); e.location = pos; e.rotation_euler = (0, 0, rz)
    e.empty_display_size = .4
    if parent: e.parent = parent
    return e

def luz(name, tipo, watts, cor, pos, col, parent=None, alvo=None, **kw):
    l = bpy.data.lights.new(name, tipo); l.energy = watts; l.color = lin(hx(cor))
    for k, v in kw.items(): setattr(l, k, v)
    ob = bpy.data.objects.new(name, l); col.objects.link(ob); ob.location = pos
    if parent: ob.parent = parent
    if alvo is not None:
        ob.rotation_euler = (Vector(alvo) - Vector(pos)).to_track_quat("-Z", "Y").to_euler()
    return ob

# ---- logotipo da operacao (imagem fornecida pelo orgao, com fundo transparente: logos/logo_lei_seca.png)
#      Sem o arquivo, a cena usa o texto "LEI SECA" no lugar.
LOGO = None
_logo_png = os.path.join(AQUI, "logos", "logo_lei_seca.png")
if os.path.exists(_logo_png):
    _img = bpy.data.images.load(_logo_png); _img.pack()
    LOGO_PROP = _img.size[0] / _img.size[1]
    LOGO = bpy.data.materials.new("Logo_Lei_Seca")
    _nt = LOGO.node_tree; _b = _nt.nodes.get("Principled BSDF")
    _t = _nt.nodes.new("ShaderNodeTexImage"); _t.image = _img
    _r = _nt.nodes.new("ShaderNodeMath"); _r.operation = "ROUND"      # transparencia recortada (glTF: alphaMode MASK)
    _nt.links.new(_t.outputs["Color"], _b.inputs["Base Color"])
    _nt.links.new(_t.outputs["Alpha"], _r.inputs[0]); _nt.links.new(_r.outputs[0], _b.inputs["Alpha"])
    _b.inputs["Roughness"].default_value = .55
    for _attr, _val in (("surface_render_method", "DITHERED"), ("blend_method", "CLIP")):
        try: setattr(LOGO, _attr, _val)
        except Exception: pass

def adesivo(name, ponto, nu, nv, col, parent=None, pos=(0, 0, 0), mat=None):
    """Adesivo com o logotipo sobre uma superficie curva: ponto(u, v) devolve a posicao 3D para u, v de 0 a 1."""
    bm = bmesh.new(); uvl = bm.loops.layers.uv.new("UVMap")
    g = [[bm.verts.new(ponto(i / nu, j / nv)) for j in range(nv + 1)] for i in range(nu + 1)]
    for i in range(nu):
        for j in range(nv):
            f = bm.faces.new((g[i][j], g[i + 1][j], g[i + 1][j + 1], g[i][j + 1]))
            for lp, (a, b) in zip(f.loops, ((i, j), (i + 1, j), (i + 1, j + 1), (i, j + 1))):
                lp[uvl].uv = (a / nu, b / nv)
    ob = finish(name, bm, pos, mat or LOGO, col, parent, smooth=True)
    return ob

def logo_lateral(name, R, col, sup_y, xc, zc, larg):
    """Logotipo colado na lateral de um veiculo, dos dois lados (legivel de fora)."""
    alt = larg / LOGO_PROP
    for lado in (1, -1):
        def ponto(u, v, lado=lado):
            x = xc + lado * (.5 - u) * larg; z = zc + (v - .5) * alt      # quem olha de fora le da esquerda para a direita
            return (x, sup_y(x, z, lado) + lado * .012, z)
        adesivo(name, ponto, 16, 6, col, R)

def logo_balao(raiz, R, zc, larg=2.5):
    alt = larg / LOGO_PROP
    for sgn in (-1, 1):
        def ponto(u, v, sgn=sgn):
            a = (u - .5) * larg / R; z = (v - .5) * alt
            r = math.sqrt(max(.01, R * R - z * z)) + .015
            return (r * math.sin(a) * (-sgn), sgn * r * math.cos(a), z)
        adesivo("Balao_Logo", ponto, 24, 8, C_BLITZ, raiz, (0, 0, zc))

# versao clara do logotipo (letras brancas), para fundos escuros como a lona azul da tenda
LOGO_CLARO = None
if LOGO:
    _w, _h = _img.size; _px = np.empty(_w * _h * 4, np.float32); _img.pixels.foreach_get(_px); _px = _px.reshape(-1, 4)
    _px[:, :3] = .94
    _img2 = bpy.data.images.new("logo_lei_seca_claro", _w, _h, alpha=True); _img2.pixels.foreach_set(_px.ravel()); _img2.pack()
    LOGO_CLARO = LOGO.copy(); LOGO_CLARO.name = "Logo_Lei_Seca_Claro"
    next(n for n in LOGO_CLARO.node_tree.nodes if n.type == "TEX_IMAGE").image = _img2

DIR_U = {"-y": (1, 0, 0), "+y": (-1, 0, 0), "-x": (0, -1, 0), "+x": (0, 1, 0)}      # para onde o logo "corre" visto de cada lado
def logo_plano(name, centro, virado, larg, col, parent=None, mat=None):
    """Logotipo numa superficie plana vertical (placas, saia da tenda), legivel de quem esta do lado 'virado'."""
    alt = larg / LOGO_PROP; du = Vector(DIR_U[virado]); c = Vector(centro)
    return adesivo(name, lambda u, v: c + du * (u - .5) * larg + Vector((0, 0, (v - .5) * alt)), 1, 1, col, parent, mat=mat)

# ================================================================== 1. RUA
RUA_X = 46.0
box("Asfalto", (2 * RUA_X, 14, .2), (0, 0, -.1), M["asfalto"], C_RUA)
for lado, y0, larg in ((1, 7.0, 5.0), (-1, -7.0, 4.0)):
    box("Meio_Fio", (2 * RUA_X, .18, .3), (0, lado * (abs(y0) + .09), 0), M["meiofio"], C_RUA, bevel=.02)
    box("Sarjeta", (2 * RUA_X, .35, .03), (0, lado * (abs(y0) - .175), .012), M["meiofio"], C_RUA)
    box("Calcada", (2 * RUA_X, larg - .18, .15), (0, lado * (abs(y0) + .18 + (larg - .18) / 2), .075), M["calcada"], C_RUA)
# faixas: divisoria central dupla amarela? via de mao unica com 4 faixas -> linhas brancas tracejadas
for y in (-3.5, 0.0, 3.5):
    x = -RUA_X + 1
    while x < RUA_X - 2:
        box("Faixa_Tracejada", (2.0, .12, .004), (x + 1, y, .003), M["faixa"], C_RUA); x += 6.0
for y in (-6.6, 6.6):
    box("Faixa_Bordo", (2 * RUA_X, .12, .004), (0, y, .003), M["faixa"], C_RUA)
for i in range(7):                                         # faixa de pedestres no fim do trecho
    box("Faixa_Pedestres", (3.0, .45, .004), (38.0, -5.4 + i * 1.8, .003), M["faixa"], C_RUA)
for x, y in ((-18, -4.2), (9, -2.1), (27, 4.8), (-33, 2.2)):   # remendos e bueiros
    box("Asfalto_Remendo", (rnd.uniform(1.2, 2.4), rnd.uniform(.8, 1.4), .004), (x, y, .002), mat("Asfalto_Remendo_%d" % x, "#252527", .95), C_RUA)
for x in (-25, 5, 30):
    cyl("Tampa_Bueiro", .32, .32, .01, (x, -1.75, .004), M["loja"], C_RUA, seg=24)
    box("Boca_de_Lobo", (.9, .12, .1), (x + 6, 6.95, .08), M["preto"], C_RUA)

# ================================================================== 2. PREDIOS (rua comercial carioca: lojas no terreo, apartamentos em cima)
def tex_porta_enrolar(S=256):
    """Porta de aco de enrolar: ripas horizontais com sujeira."""
    y, x = np.mgrid[0:S, 0:S] / S
    ripa = (y * 12) % 1
    a = np.ones((S, S, 3)) * np.array(hx("#7b8087"))
    a *= (.72 + .28 * np.sin(ripa * PI) ** .5)[..., None]
    a[ripa < .08] *= .45
    r = np.random.default_rng(9); a *= (1 + .06 * r.standard_normal((S, S, 1)))
    a *= (1 - .25 * np.clip(y - .75, 0, 1) * 4)[..., None]          # mais sujo embaixo
    return np.clip(a, 0, 1)

def tex_pastilha(cor, S=256, n=20):
    """Revestimento de pastilhas, comum nos predios dos anos 60 e 70."""
    r = np.random.default_rng(int(sum(cor) * 1000))
    cel = S // n
    g = r.uniform(.84, 1.08, (n, n, 1)); a = np.kron(g, np.ones((cel, cel, 1))) * np.array(cor)
    a = np.pad(a, ((0, S - a.shape[0]), (0, S - a.shape[1]), (0, 0)), mode="edge")
    yy, xx = np.mgrid[0:S, 0:S]
    a[(xx % cel == 0) | (yy % cel == 0)] = np.array(hx("#8d8a84"))
    return np.clip(a, 0, 1)

M.update({
    "porta_enrolar": img_mat("Porta_Enrolar", np_image("porta_enrolar", tex_porta_enrolar()), 1.0, .45),
    "pastilha_a": img_mat("Pastilha_Verde", np_image("pastilha_verde", tex_pastilha(hx("#8fa89a"))), .5, .35),
    "pastilha_b": img_mat("Pastilha_Azul", np_image("pastilha_azul", tex_pastilha(hx("#8a9db5"))), .5, .35),
    "esquadria": mat("Esquadria_Aluminio", "#3a3d42", .4, .7),
    "ar_cond": mat("Ar_Condicionado", "#d6d4cc", .5),
    "vitrine": mat("Vitrine_Acesa", "#40382a", .2, emit="#ffe2b0", forca=2.2),
    "rodape": mat("Rodape_Granito", "#2e2d2c", .35),
    "caixa_dagua": mat("Caixa_Dagua", "#3b6fb5", .6),
    "guarda": mat("Guarda_Corpo_Metal", "#2b2d30", .5, .6),
    "vidro_var": mat("Vidro_Varanda", "#7fa0a8", .08, alpha=.3),
    "cortina": mat("Janela_Cortina", "#2a2622", .8, emit="#d9b98a", forca=.45),
})
M["texto_letreiro"] = mat("Texto_Letreiro", "#ffffff", .5, emit="#ffffff", forca=1.4)
LETREIROS = [mat("Letreiro_%d" % i, c, .5, emit=c, forca=.35) for i, c in enumerate(("#b3261e", "#1f5fa8", "#1e7a46", "#d98a12", "#5b2a86", "#222428"))]
LOJAS = ["FARMÁCIA", "PADARIA", "LANCHONETE", "MERCADINHO", "CHAVEIRO", "PAPELARIA", "ÓTICA", "BAR E PETISCOS", "LOTÉRICA", "CASA DE SUCOS",
         "BARBEARIA", "ARMARINHO", "AÇOUGUE", "FLORICULTURA", "LAVANDERIA", "SAPATARIA", "HORTIFRUTI", "ASSISTÊNCIA TÉCNICA"]
rnd.shuffle(LOJAS)
_loja = [0]

def predio(nome, x0, x1, y_frente, lado, altura, cor, andares, estilo):
    """estilo: 0 pilastras e janelas simples · 1 varandas de alvenaria · 2 faixas horizontais (modernista) · 3 varandas de vidro"""
    prof = 9.0; w = x1 - x0; xc = (x0 + x1) / 2; yc = y_frente + lado * prof / 2
    v = "-y" if lado > 0 else "+y"
    F = lambda d: y_frente - lado * d                       # d metros para fora da fachada (em direcao a rua)
    C = C_PRED
    box(nome, (w, prof, altura), (xc, yc, altura / 2 + .15), cor, C)
    # ---- terreo comercial
    box(nome + "_Rodape", (w, .08, .55), (xc, F(.03), .42), M["rodape"], C)
    nl = max(2, int(w // 4.3)); pl = w / nl
    for j in range(nl + 1):
        box(nome + "_Pilar", (.42, .16, 3.35), (min(max(x0 + pl * j, x0 + .21), x1 - .21), F(.07), 1.82), M["concreto"], C)
    for j in range(nl):
        x = x0 + pl * (j + .5); lv = pl - .62
        aberta = False                                         # todas as lojas fechadas (operacao noturna)
        if aberta:
            box(nome + "_Vitrine", (lv, .05, 2.55), (x, F(.02), 1.45), M["vitrine"], C)
            box(nome + "_Vitrine_Caixilho", (lv, .07, .08), (x, F(.04), 2.72), M["esquadria"], C)
            box(nome + "_Vitrine_Caixilho", (.07, .07, 2.55), (x + lv * .22, F(.04), 1.45), M["esquadria"], C)
        else:
            box(nome + "_Porta_Loja", (lv, .06, 3.22), (x, F(.02), 1.78), M["porta_enrolar"], C)
            box(nome + "_Porta_Loja_Guia", (lv + .1, .1, .16), (x, F(.04), 3.44), M["esquadria"], C)
    box(nome + "_Marquise", (w, 1.35, .16), (xc, F(.67), 3.66), M["concreto"], C)
    box(nome + "_Marquise_Testeira", (w, .06, .3), (xc, F(1.33), 3.6), M["concreto"], C)
    # ---- andares
    hand = (altura - 4.2) / andares; nj = max(2, int(w // 2.7)); passo = w / nj
    varanda = estilo in (1, 3)
    for a in range(andares):
        z0 = 4.35 + hand * a
        if estilo == 2:
            box(nome + "_Faixa_Peitoril", (w, .1, hand * .3), (xc, F(.04), z0 + hand * .14), M["concreto"], C)
        for j in range(nj):
            x = x0 + passo * (j + .5); r = rnd.random()
            m = M["janela_on"] if r < .17 else M["janela_on2"] if r < .23 else M["cortina"] if r < .34 else M["janela_off"]
            jw = passo * (.72 if estilo == 2 else .56); jh = hand * (.46 if estilo == 2 else .5); zc = z0 + hand * .56
            box(nome + "_Moldura", (jw + .14, .1, jh + .14), (x, F(.03), zc), M["esquadria"], C)
            box(nome + "_Janela", (jw, .03, jh), (x, F(.075), zc), m, C)
            box(nome + "_Janela_Montante", (.05, .04, jh), (x, F(.085), zc), M["esquadria"], C)
            if not varanda:
                box(nome + "_Peitoril", (jw + .3, .2, .07), (x, F(.1), zc - jh / 2 - .1), M["concreto"], C)
                if rnd.random() < .28:
                    box(nome + "_Ar_Cond", (.66, .42, .42), (x + rnd.uniform(-.2, .2) * jw, F(.2), zc - jh / 2 - .38), M["ar_cond"], C, bevel=.02)
                    box(nome + "_Ar_Cond_Grade", (.56, .02, .3), (x, F(.415), zc - jh / 2 - .38), M["esquadria"], C)
        if varanda:
            box(nome + "_Varanda_Laje", (w - .5, 1.05, .12), (xc, F(.52), z0 + .02), M["concreto"], C)
            if estilo == 1:
                box(nome + "_Varanda_Mureta", (w - .5, .1, .95), (xc, F(1.0), z0 + .55), cor, C)
            else:
                box(nome + "_Varanda_Vidro", (w - .5, .02, .85), (xc, F(1.02), z0 + .5), M["vidro_var"], C)
                box(nome + "_Varanda_Guarda", (w - .5, .05, .05), (xc, F(1.02), z0 + .97), M["guarda"], C)
            for k in range(1, nj):                               # divisorias entre os apartamentos
                box(nome + "_Varanda_Divisoria", (.08, 1.0, hand - .15), (x0 + passo * k, F(.5), z0 + hand / 2), cor, C)
    if estilo == 0:                                              # pilastras marcando a fachada
        for k in range(0, nj + 1, 2):
            box(nome + "_Pilastra", (.3, .12, altura - 4.2), (min(max(x0 + passo * k, x0 + .15), x1 - .15), F(.05), 4.2 + (altura - 4.2) / 2 + .15), M["concreto"], C)
    # ---- topo: cornija, platibanda, caixa d'agua e casa de maquinas
    box(nome + "_Cornija", (w + .1, .4, .22), (xc, F(.1), altura + .15), M["concreto"], C)
    box(nome + "_Platibanda", (w, .2, .7), (xc, F(-.1), altura + .5), cor, C)
    cx = xc + rnd.uniform(-.25, .25) * w
    box(nome + "_Casa_Maquinas", (3.0, 3.0, 2.2), (cx, yc, altura + 1.25), M["concreto"], C)
    cyl(nome + "_Caixa_Dagua", .85, .85, 1.3, (cx + rnd.choice((-2.6, 2.6)), yc + .5, altura + .8), M["caixa_dagua"], C, seg=14)

cores = [M["reboco_a"], M["pastilha_a"], M["reboco_c"], M["reboco_d"], M["reboco_b"], M["pastilha_b"]]
for lado, yf in ((1, 12.0), (-1, -11.0)):
    x = -RUA_X; i = 0
    while x < RUA_X - 1:
        w = min(rnd.choice((12, 15, 18, 21)), RUA_X - x); and_ = rnd.choice((3, 4, 5, 6, 7))
        predio("Predio_%s_%d" % ("N" if lado > 0 else "S", i), x + .15, x + w - .15, yf, lado, 4.2 + and_ * 3.0, cores[(i * 5 + (lado > 0) * 2) % 6], and_, (i + (lado < 0)) % 4)
        x += w; i += 1

# ================================================================== 3. ARVORES E POSTES
def arvore(nome, x, y, h=5.5):
    box(nome + "_Canteiro", (1.3, 1.3, .04), (x, y, .16), M["terra"], C_VEG)
    torno(nome + "_Tronco", [(.2, 0), (.16, .6), (.13, h * .55), (.09, h * .75)], M["tronco"], C_VEG, pos=(x, y, .15), seg=10)
    for k in range(5):
        bm = bmesh.new(); bmesh.ops.create_icosphere(bm, subdivisions=2, radius=rnd.uniform(1.1, 1.7))
        for v in bm.verts: v.co *= rnd.uniform(.82, 1.12)
        a = rnd.uniform(0, 2 * PI); d = rnd.uniform(0, 1.2) if k else 0
        finish(nome + "_Copa", bm, (x + d * math.cos(a), y + d * math.sin(a), h * .78 + rnd.uniform(-.3, .9)), M["folha"], C_VEG, smooth=True)

for i, x in enumerate((-36, -26, 16, 27, 37)):
    arvore("Arvore_N_%d" % i, x, 8.3, rnd.uniform(5, 6.5))
for i, x in enumerate((-40, -29, -18, -6, 6, 18, 30, 41)):
    arvore("Arvore_S_%d" % i, x, -8.2, rnd.uniform(4.8, 6.2))

def poste(nome, x, y, lado):
    cyl(nome + "_Fuste", .07, .1, 8.4, (x, y, 4.35), M["poste"], C_VEG, seg=12)
    barra(nome + "_Braco", (x, y, 8.4), (x, y - lado * 2.2, 8.75), .045, M["poste"], C_VEG)
    box(nome + "_Luminaria", (.3, .7, .12), (x, y - lado * 2.4, 8.72), M["poste"], C_VEG, bevel=.03)
    box(nome + "_Difusor", (.22, .5, .02), (x, y - lado * 2.4, 8.65), M["lamp"], C_VEG)
    luz(nome + "_Luz", "POINT", 650, "#ffd9a0", (x, y - lado * 2.4, 8.5), C_LUZ, shadow_soft_size=.25)

for i, x in enumerate((-33, -11, 11, 33)):
    poste("Poste_N_%d" % i, x, 7.6, 1)
for i, x in enumerate((-22, 0, 22, 44)):
    poste("Poste_S_%d" % i, x, -7.6, -1)

# ================================================================== 4. ESTRUTURA DA BLITZ
# ---- balao inflavel iluminado
def balao(x, y):
    R, zc = 1.55, 3.6
    raiz = vazio("Balao_Lei_Seca", (x, y, 0), C_BLITZ)
    bm = bmesh.new(); bmesh.ops.create_uvsphere(bm, u_segments=32, v_segments=16, radius=R)
    for f in bm.faces:                                     # gomos azuis em triangulo no topo e na base
        c = f.calc_center_median(); lat = math.asin(max(-1, min(1, c.z / R))); lon = math.atan2(c.y, c.x)
        dente = abs(((lon / (2 * PI) * 6) % 1) - .5) * 2    # 0 no meio do gomo, 1 na borda
        f.material_index = 1 if abs(lat) > .5 + .55 * dente else 0
    finish("Balao_Lona", bm, (0, 0, zc), [M["lona_balao"], M["lona_balao_az"]], C_BLITZ, raiz, smooth=True)
    if LOGO: logo_balao(raiz, R, zc)
    for virado, sgn in ((("-y", -1), ("+y", 1)) if not LOGO else ()):             # LEI SECA dos dois lados, acompanhando a curva
        me = texto_malha("LEI SECA", .52); me.materials.append(M["texto_az"])
        for v in me.vertices:
            a = v.co.x / R; r = math.sqrt(max(.01, R * R - v.co.y ** 2)) + .012
            v.co = Vector((r * math.sin(a) * (-sgn), sgn * r * math.cos(a), v.co.y))
        ob = bpy.data.objects.new("Balao_Texto", me); C_BLITZ.objects.link(ob); ob.parent = raiz; ob.location = (0, 0, zc)
    torno("Balao_Base", [(.0, 0), (.62, 0), (.66, .25), (.6, .8), (.42, 1.6), (.5, 2.2)], M["azul"], C_BLITZ, raiz, seg=20)
    box("Balao_Soprador", (.45, .4, .35), (.85, .2, .33), M["preto"], C_BLITZ, raiz, bevel=.05)
    for a in (0.6, 2.7, 4.6):                               # estais ate os pesos
        px, py = 2.6 * math.cos(a), 1.5 * math.sin(a)
        barra("Balao_Estai", (R * .7 * math.cos(a), R * .7 * math.sin(a), zc + .2), (px, py, .25), .006, M["branco"], C_BLITZ, raiz, seg=5)
        cyl("Balao_Peso", .13, .15, .22, (px, py, .26), M["preto"], C_BLITZ, raiz, seg=12)
    luz("Balao_Luz", "POINT", 350, "#f2f5ff", (x, y, zc), C_LUZ, shadow_soft_size=1.5)
balao(-17.0, 9.3)

# ---- moveis de plastico
def cadeira(nome, x, y, rz, col=C_BLITZ):
    r = vazio(nome, (x, y, 0), col, rz)
    box(nome + "_Assento", (.44, .44, .035), (0, 0, .44), M["branco"], col, r, bevel=.015)
    box(nome + "_Encosto", (.42, .03, .42), (0, .215, .7), M["branco"], col, r, rot=(-.14, 0, 0), bevel=.012)
    for sx in (-1, 1):
        box(nome + "_Braco", (.04, .4, .03), (sx * .22, .02, .64), M["branco"], col, r, bevel=.01)
        for sy in (-1, 1):
            barra(nome + "_Pe", (sx * .19, sy * .19, .44), (sx * .23, sy * .23, 0), .017, M["branco"], col, r, seg=6)
    return r

def mesa(nome, x, y, rz=0.0, tam=(1.2, .7), m=None, col=C_BLITZ, toalha=None):
    r = vazio(nome, (x, y, 0), col, rz); w, d = tam
    box(nome + "_Tampo", (w, d, .035), (0, 0, .725), m or M["branco"], col, r, bevel=.012)
    for sx in (-1, 1):
        for sy in (-1, 1):
            cyl(nome + "_Pe", .022, .022, .71, (sx * (w / 2 - .08), sy * (d / 2 - .08), .355), M["metal"], col, r, seg=8)
    if toalha:
        box(nome + "_Toalha", (w + .03, d + .03, .5), (0, 0, .5), toalha, col, r)
        box(nome + "_Toalha_Topo", (w + .03, d + .03, .012), (0, 0, .75), toalha, col, r)
    return r

# ---- tenda 3 x 3 m
def tenda(x, y):
    r = vazio("Tenda_Lei_Seca", (x, y, 0), C_BLITZ); L, H, HP = 1.5, 2.15, 3.05
    for sx in (-1, 1):
        for sy in (-1, 1):
            cyl("Tenda_Perna", .022, .022, H, (sx * L, sy * L, H / 2), M["branco"], C_BLITZ, r, seg=8)
            barra("Tenda_Trelica", (sx * L, sy * L, H), (0, 0, HP - .12), .012, M["branco"], C_BLITZ, r, seg=6)
            cyl("Tenda_Sapata", .07, .07, .012, (sx * L, sy * L, .006), M["metal"], C_BLITZ, r, seg=10)
    e = .06
    vs = [(-L - e, -L - e, H), (L + e, -L - e, H), (L + e, L + e, H), (-L - e, L + e, H), (0, 0, HP)]
    malha("Tenda_Cobertura", vs, [(0, 1, 4), (1, 2, 4), (2, 3, 4), (3, 0, 4)], M["azul"], C_BLITZ, r)
    for (ax, ay, tam, virado) in ((0, -1, (2 * L + .14, .012, .3), "-y"), (0, 1, (2 * L + .14, .012, .3), "+y"),
                                  (-1, 0, (.012, 2 * L + .14, .3), "-x"), (1, 0, (.012, 2 * L + .14, .3), "+x")):
        box("Tenda_Saia", tam, (ax * (L + e), ay * (L + e), H - .15), M["azul"], C_BLITZ, r)
        (logo_plano("Tenda_Logo", (ax * (L + e + .009), ay * (L + e + .009), H - .15), virado, .8, C_BLITZ, r, LOGO_CLARO) if LOGO else texto("Tenda_Texto", "LEI SECA", .19, (ax * (L + e + .009), ay * (L + e + .009), H - .15), virado, M["texto_br"], C_BLITZ, r))
    for k, mx in enumerate((-.68, .68)):
        mesa("Tenda_Mesa_%d" % k, x + mx, y + .25)
    cadeira("Tenda_Cadeira_0", x - .7, y + .95, 0); cadeira("Tenda_Cadeira_1", x + .7, y + .95, 0)
    cadeira("Tenda_Cadeira_2", x - 1.0, y - .7, PI * .92); cadeira("Tenda_Cadeira_3", x - 2.2, y - .2, PI * .6)
    # notebook, impressora termica e pranchetas
    nb = vazio("Notebook", (x - .7, y + .25, .745), C_BLITZ, PI, )
    box("Notebook_Base", (.34, .24, .016), (0, 0, .008), M["metal"], C_BLITZ, nb, bevel=.004)
    box("Notebook_Tampa", (.34, .012, .23), (0, .125, .125), M["metal"], C_BLITZ, nb, rot=(-.22, 0, 0))
    box("Notebook_Tela", (.31, .004, .2), (0, .117, .127), M["tela"], C_BLITZ, nb, rot=(-.22, 0, 0))
    box("Impressora_Termica", (.16, .2, .11), (x + .95, y + .3, .8), M["preto"], C_BLITZ, bevel=.02)
    box("Bobina_Papel", (.1, .005, .09), (x + .95, y + .2, .87), M["papel"], C_BLITZ, rot=(.5, 0, 0))
    for k in range(2):
        box("Prancheta_%d" % k, (.23, .32, .008), (x + .35 + k * .28, y + .2, .747), M["loja"], C_BLITZ, rot=(0, 0, .15 - k * .3))
        box("Prancheta_Papel_%d" % k, (.21, .29, .003), (x + .35 + k * .28, y + .2, .753), M["papel"], C_BLITZ, rot=(0, 0, .15 - k * .3))
tenda(-10.0, 5.4)

# ---- torre de iluminacao portatil (tripe)
TORRES = []
def torre(i, x, y, alvo):
    nome = "Torre_Luz_%d" % i; r = vazio(nome, (x, y, 0), C_BLITZ)
    for k in range(3):
        a = k * 2 * PI / 3 + i
        barra(nome + "_Pe", (0, 0, .95), (.55 * math.cos(a), .55 * math.sin(a), 0), .016, M["tripe"], C_BLITZ, r, seg=6)
        barra(nome + "_Trava", (0, 0, .45), (.3 * math.cos(a), .3 * math.sin(a), .43), .01, M["tripe"], C_BLITZ, r, seg=5)
    cyl(nome + "_Mastro", .018, .022, 2.5, (0, 0, 1.55), M["tripe"], C_BLITZ, r, seg=8)
    d = (Vector(alvo) - Vector((x, y, 2.9))); rz = math.atan2(d.y, d.x) - PI / 2
    cab = vazio(nome + "_Cabeca", (0, 0, 2.9), C_BLITZ, rz, r)
    box(nome + "_Travessa", (.7, .03, .03), (0, 0, -.06), M["preto"], C_BLITZ, cab)
    for sx in (-1, 1):
        box(nome + "_Refletor", (.3, .07, .22), (sx * .19, 0, .06), M["preto"], C_BLITZ, cab, rot=(-.5, 0, 0), bevel=.012)
        box(nome + "_LED", (.27, .008, .19), (sx * .19, .034, .043), M["led"], C_BLITZ, cab, rot=(-.5, 0, 0))
    luz(nome + "_Luz", "SPOT", 650, "#f4f7ff", (x + d.normalized().x * .1, y + d.normalized().y * .1, 2.92), C_LUZ, alvo=alvo,
        spot_size=math.radians(115), spot_blend=.5, shadow_soft_size=.12)
    TORRES.append((x, y, 2.9))
torre(0, -13.2, 3.5, (-9.5, 2.0, 0)); torre(1, -3.3, 3.6, (-6.5, 1.6, 0)); torre(2, 6.2, 3.7, (9.5, 1.8, 0)); torre(3, 16.0, 3.6, (12.5, 1.5, 0))
torre(4, -8.0, 7.3, (-10, 5.2, 0))

# ================================================================== 5. CONES, BARREIRAS, CAVALETES
CONE_PERFIL = [(.0, .75), (.03, .75), (.055, .55), (.075, .42), (.1, .27), (.118, .14), (.14, .03)]
def cone(i, x, y):
    r = vazio("Cone_%02d" % i, (x, y, 0), C_SINAL, rnd.uniform(0, 1.5))
    torno("Cone_%02d_Corpo" % i, CONE_PERFIL, [M["cone"], M["refletivo"]], C_SINAL, r, seg=16, idx=[0, 0, 1, 0, 1, 0])
    box("Cone_%02d_Base" % i, (.36, .36, .03), (0, 0, .015), M["cone"], C_SINAL, r, bevel=.01)
n = 0
for k in range(9):                                         # funil: fecha as duas faixas da blitz (de quem vem de -X)
    t = k / 8; cone(n, -41 + t * 13, 6.7 - t * 6.5); n += 1
for x in np.arange(-22.0, 27.1, 3.5):                      # linha entre a area da blitz e as faixas livres
    if -3.5 < x < 3.5: continue                          # vao de saida: o veiculo liberado volta ao transito por aqui
    cone(n, float(x), .2); n += 1
for k in range(4):                                         # saida: devolve os veiculos liberados ao transito
    cone(n, 29 + k * 2.2, .9 + k * 1.6); n += 1
for x in np.arange(-19.0, 25.0, 4.2):                      # separa a faixa de abordagem da faixa de apoio
    if abs(x + 7) < 4.5 or abs(x - 8.5) < 3.2: continue    # vaos: ponto de abordagem e mesa de teste
    cone(n, float(x), 3.55); n += 1

def barreira(i, x, y, rz):
    r = vazio("Barreira_%d" % i, (x, y, 0), C_SINAL, rz)
    vs = [(-.75, -.24, 0), (.75, -.24, 0), (.75, .24, 0), (-.75, .24, 0), (-.75, -.09, .82), (.75, -.09, .82), (.75, .09, .82), (-.75, .09, .82)]
    fs = [(0, 3, 2, 1), (4, 5, 6, 7), (0, 1, 5, 4), (1, 2, 6, 5), (2, 3, 7, 6), (3, 0, 4, 7)]
    ob = malha("Barreira_%d_Corpo" % i, vs, fs, M["barreira"], C_SINAL, r)
    b = ob.modifiers.new("Chanfro", "BEVEL"); b.width = .04; b.segments = 2
    for sy in (-1, 1):
        box("Barreira_%d_Faixa" % i, (1.3, .012, .16), (0, sy * .185, .45), M["refletivo"], C_SINAL, r, rot=(sy * -.18, 0, 0))
for i, (x, y, rz) in enumerate(((-24.5, 5.9, 1.25), (-24.9, 4.3, 1.25), (-12.6, 6.9, 0), (24.5, 4.6, 1.57), (24.5, 6.3, 1.57), (-27.0, 6.4, 1.25))):
    barreira(i, x, y, rz)

def cavalete(i, x, y, rz, linha2="FISCALIZAÇÃO"):
    r = vazio("Cavalete_%d" % i, (x, y, 0), C_SINAL, rz)
    for sy in (-1, 1):
        p = box("Cavalete_%d_Painel" % i, (.9, .02, 1.05), (0, sy * .17, .62), M["branco"], C_SINAL, r, rot=(sy * .27, 0, 0))
        box("Cavalete_%d_Borda" % i, (.96, .016, 1.11), (0, -sy * .004, 0), M["azul"], C_SINAL, p)
        v = "-y" if sy < 0 else "+y"
        (logo_plano("Cavalete_%d_Logo" % i, (0, sy * .012, .2), v, .8, C_SINAL, p) if LOGO else texto("Cavalete_%d_Texto" % i, "LEI SECA", .15, (0, sy * .012, .2), v, M["texto_az"], C_SINAL, p))
        texto("Cavalete_%d_Sub" % i, linha2, .065, (0, sy * .012, -.02), v, M["texto_pr"], C_SINAL, p)
        box("Cavalete_%d_Tarja" % i, (.8, .004, .1), (0, sy * .011, -.3), M["azul"], C_SINAL, p)
        texto("Cavalete_%d_Tarja_Texto" % i, "REDUZA A VELOCIDADE", .045, (0, sy * .014, -.3), v, M["texto_br"], C_SINAL, p)
    barra("Cavalete_%d_Trava" % i, (.4, -.2, .35), (.4, .2, .35), .008, M["metal"], C_SINAL, r, seg=5)
cavalete(0, -30.0, 4.6, PI / 2); cavalete(1, -20.5, 3.5, PI / 2, "PARE AO SINAL DO AGENTE"); cavalete(2, 5.2, 1.0, PI / 2 + .5, "ÁREA DE TESTE")

# marca no chao do ponto de abordagem
box("Marca_Ponto_Abordagem", (.12, 2.6, .004), (-4.75, 1.9, .003), M["faixa_am"], C_RUA)
texto("Marca_Texto_Pare", "PARE", .7, (-3.6, 1.9, .004), (0, 0, -PI / 2), M["faixa"], C_RUA)

# ================================================================== 6. VEICULOS
# secoes do "loft": x, z_baixo, z_ombro (linha de cintura), z_topo (teto ou capo), meia largura, meia largura do teto (None = capo)
EST_SUV = [
    (2.17, .45, .70, .74, .66, None), (2.13, .36, .76, .80, .78, None), (2.02, .31, .82, .86, .85, None),
    (1.75, .29, .88, .92, .89, None), (1.40, .28, .92, .96, .905, None), (1.00, .28, .97, 1.01, .91, None),
    (.72, .28, 1.00, 1.32, .91, .80), (.32, .28, 1.01, 1.62, .91, .76), (.10, .28, 1.01, 1.655, .91, .755),
    (-.12, .28, 1.01, 1.665, .91, .755), (-.28, .28, 1.01, 1.67, .91, .755), (-.70, .28, 1.015, 1.67, .91, .755),
    (-1.05, .28, 1.02, 1.665, .91, .75), (-1.25, .28, 1.02, 1.66, .91, .75), (-1.55, .29, 1.02, 1.645, .905, .74),
    (-1.80, .30, 1.02, 1.62, .90, .725), (-1.92, .31, 1.01, 1.58, .89, .71), (-2.05, .33, 1.00, 1.40, .87, .68),
    (-2.13, .36, .99, 1.10, .82, .62), (-2.17, .44, .96, 1.00, .74, .55),
]
def escala_est(est, sx, sz, sw):
    return [(x * sx, zb * (.75 + .25 * sz), zs * sz, zt * sz, hw * sw, None if hr is None else hr * sw) for x, zb, zs, zt, hw, hr in est]
EST_HATCH = escala_est(EST_SUV, .93, .885, .945)            # hatch compacto ~4,0 x 1,72 x 1,48 m
EST_VAN = [
    (2.72, .50, .86, .90, .78, None), (2.66, .40, .96, 1.0, .92, None), (2.45, .34, 1.06, 1.12, .99, None), (2.05, .32, 1.16, 1.24, 1.01, None),
    (1.80, .32, 1.22, 1.62, 1.01, .9), (1.40, .32, 1.26, 2.30, 1.01, .92), (1.15, .32, 1.27, 2.46, 1.01, .93), (.95, .32, 1.27, 2.50, 1.01, .94),
    (.45, .32, 1.27, 2.51, 1.01, .94), (.25, .32, 1.27, 2.51, 1.01, .94), (-.6, .32, 1.27, 2.51, 1.01, .94), (-1.6, .32, 1.27, 2.51, 1.01, .94),
    (-2.4, .33, 1.27, 2.50, 1.01, .94), (-2.62, .35, 1.26, 2.47, 1.0, .92), (-2.7, .42, 1.24, 2.40, .96, .88), (-2.72, .5, 1.2, 2.3, .9, .82),
]

def veiculo(nome, col, pos, rz, est, pint, faixa=None, tipo="suv", aro=None, janela_aberta=False, placa="RIO2A26"):
    """Carroceria em loft + rodas + farois + interior. tipo: suv | hatch | van. Frente do veiculo para +X local."""
    R = vazio(nome, pos, col, rz)
    aro = aro or M["aro"]
    xs = [e[0] for e in est]; comp = xs[0] - xs[-1]; hw_max = max(e[4] for e in est)
    # limites das janelas, relativos ao inicio/fim da cabine
    cab = [e for e in est if e[5] is not None]; xa, xd = cab[0][0], cab[-1][0]
    teto_x = [e[0] for e in cab if e[3] >= max(c[3] for c in cab) - .06]
    pb0, pb1 = teto_x[0], xa                                # para-brisa: do inicio da cabine ate o inicio do teto
    def meia(e):
        x, zb, zs, zt, hw, hr = e
        p = [(0, zb), (hw * .82, zb), (hw * .97, zb + .07), (hw, zb + .22), (hw, zb + .40), (hw * .995, zs - .06), (hw * .975, zs)]
        if hr is None: p += [(hw * .9, zt - .015), (hw * .75, zt), (hw * .45, zt + .01), (0, zt + .015)]
        else: p += [(hr + .025, zs + .04), (hr, zt - .07), (hr * .86, zt), (0, zt + .01)]
        return p
    L = pb0 - xd                                            # comprimento do teto ate a traseira
    def mf(j, xm):
        if j <= 2: return 2
        if j == 3: return 1
        if j <= 6: return 0
        para_brisa = pb0 <= xm <= pb1
        if tipo == "van":
            if j == 7: return 3 if (pb0 - 1.05 <= xm <= pb0 - .08) else 4 if para_brisa else 0
            return 3 if para_brisa else 0
        vigia = xm <= cab[-4][0]
        if j == 7:
            if para_brisa or vigia: return 4
            t = (pb0 - xm) / L                                 # 0 = coluna A, 1 = traseira
            if t < .245: return 3
            if t < .31: return 4
            if t < .62: return 3
            if t < .70: return 4
            if t < .93: return 3
            return 0
        return 3 if (para_brisa or vigia) else 0
    bm = bmesh.new(); aneis = []
    for e in est:
        h = meia(e); pts = h + [(-y, z) for (y, z) in reversed(h[1:-1])]
        aneis.append([bm.verts.new((e[0], y, z)) for (y, z) in pts])
    N = len(aneis[0]); NH = len(meia(est[0])) - 1; abertas = []
    for i in range(len(est) - 1):
        for k in range(N):
            k2 = (k + 1) % N
            f = bm.faces.new((aneis[i][k], aneis[i][k2], aneis[i + 1][k2], aneis[i + 1][k]))
            j = k if k < NH else (N - 1 - k); xm = (est[i + 1][0] + est[i][0]) / 2
            f.material_index = mf(j, xm)
            if janela_aberta and j == 7 and k < NH and f.material_index == 3 and (pb0 - xm) / L < .245: abertas.append(f)
    for anel in (aneis[0], aneis[-1]):
        c = bm.verts.new((anel[0].co.x, 0, sum(v.co.z for v in anel) / N))
        for k in range(N): bm.faces.new((anel[k], anel[(k + 1) % N], c)).material_index = 0
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
    vinco = bm.edges.layers.float.new("crease_edge")
    for i in range(len(est) - 1):
        for jj, forca in ((3, .95), (4, .95), (6, .8), (7, .85), (9, .45)):
            for k in (jj, N - jj):
                e = bm.edges.get((aneis[i][k % N], aneis[i + 1][k % N]))
                if e: e[vinco] = forca
    for i in (0, len(est) - 1):
        for k in range(N):
            e = bm.edges.get((aneis[i][k], aneis[i][(k + 1) % N]))
            if e: e[vinco] = .7
    if abertas: bmesh.ops.delete(bm, geom=abertas, context="FACES")
    corpo = finish(nome + "_Carroceria", bm, (0, 0, 0), [pint, faixa or pint, M["plast"], M["vidro"], M["preto_b"]], col, R, smooth=True)
    s = corpo.modifiers.new("Suavizar", "SUBSURF"); s.levels = 1; s.render_levels = 1
    # rodas
    rr = {"suv": .35, "hatch": .31, "van": .36}[tipo]
    eixos = {"suv": (1.33, -1.34), "hatch": (1.24, -1.25), "van": (1.78, -1.62)}[tipo]
    bm = bmesh.new()
    for x in eixos:
        bmesh.ops.create_cone(bm, cap_ends=True, segments=32, radius1=rr + .05, radius2=rr + .05, depth=2.6,
                              matrix=Matrix.Translation((x, 0, rr + .01)) @ Matrix.Rotation(PI / 2, 4, "X"))
    cort = finish(nome + "_Cortador", bm, (0, 0, 0), M["plast"], col, R); cort.display_type = "WIRE"; cort.hide_render = True; cort.hide_viewport = True
    cort["cortador"] = True
    b = corpo.modifiers.new("Caixas_de_Roda", "BOOLEAN"); b.object = cort; b.solver = "EXACT"
    corpo.modifiers.move(1, 0)
    k = rr / .35
    PNEU = [(.215 * k, -.105), (.29 * k, -.112), (.325 * k, -.105), (.343 * k, -.08), (.35 * k, -.04), (.35 * k, .04), (.343 * k, .08), (.325 * k, .105), (.29 * k, .112), (.215 * k, .105)]
    ARO = [(0, .085), (.06 * k, .085), (.075 * k, .07), (.2 * k, .07), (.215 * k, .095), (.217 * k, -.09), (.2 * k, -.095)]
    for x in eixos:
        cyl(nome + "_Forro_Caixa", rr + .045, rr + .045, hw_max * 1.78, (x, 0, rr + .01), M["plast"], col, R, rot=(PI / 2, 0, 0), seg=24)
        for lado in (1, -1):
            g = vazio(nome + "_Roda", (x, lado * (hw_max - .12), rr), col, 0, R); g.rotation_euler = (-lado * PI / 2, 0, 0)
            torno(nome + "_Pneu", PNEU, M["pneu"], col, g, seg=28)
            torno(nome + "_Aro", ARO, aro, col, g, seg=24)
            for q in range(5):
                a = 2 * PI * q / 5
                box(nome + "_Raio", (.15 * k, .04, .03), (math.cos(a) * .135 * k, math.sin(a) * .135 * k, .075), aro, col, g, rot=(0, 0, a))
            cyl(nome + "_Disco", .16 * k, .16 * k, .022, (0, 0, -.02), M["disco"], col, g, seg=20)
    # superficie da carroceria (para colar pecas)
    bpy.context.view_layer.update()
    ev = corpo.evaluated_get(bpy.context.evaluated_depsgraph_get())
    def sup_y(x, z, lado):
        ok, lc, _, _ = ev.ray_cast(Vector((x, lado * 2.5, z)), Vector((0, -lado, 0)))
        return lc.y if ok else lado * hw_max
    def sup_x(y, z, ponta):
        ok, lc, _, _ = ev.ray_cast(Vector((ponta * 4.0, y, z)), Vector((-ponta, 0, 0)))
        return lc.x if ok else ponta * comp / 2
    zf = est[2][2]                                          # altura da cintura na frente
    xfr, xtr = xs[0], xs[-1]
    box(nome + "_Parachoque_Diant", (.22, hw_max * 1.94, .28), (xfr - .08, 0, est[0][1] + .03), M["plast"], col, R, bevel=.08, seg=3)
    box(nome + "_Grade", (.06, hw_max * 1.1, .18), (sup_x(0, zf - .16, 1) + .0, 0, zf - .16), M["preto_b"], col, R, bevel=.035, seg=2)
    box(nome + "_Parachoque_Tras", (.22, hw_max * 1.92, .28), (xtr + .06, 0, est[-1][1] + .06), M["plast"], col, R, bevel=.08, seg=3)
    zl = est[-2][2] - (.14 if tipo != "van" else .1)
    for lado in (1, -1):
        xf = sup_x(lado * hw_max * .66, zf - .07, 1)
        box(nome + "_Farol", (.1, hw_max * .4, .12), (xf - .02, lado * hw_max * .64, zf - .06), M["farol"], col, R, rot=(0, 0, -lado * .25), bevel=.03, seg=2)
        xt = sup_x(lado * hw_max * .8, zl, -1)
        box(nome + "_Lanterna", (.07, .15, .3 if tipo != "van" else .5), (xt + .015, lado * hw_max * .78, zl), M["lanterna"], col, R, rot=(0, 0, lado * .3), bevel=.022, seg=2)
        zr = est[len(est) // 3][2] + .1; xr = pb1 - .1
        box(nome + "_Retrovisor", (.1, .2, .13), (xr, lado * (hw_max + .1), zr), M["plast"] if tipo == "van" else pint, col, R, bevel=.04, seg=3)
        box(nome + "_Retrovisor_Base", (.1, .12, .04), (xr + .03, lado * (hw_max + .0), zr - .05), M["plast"], col, R, bevel=.012)
        for t in ((.12, .5) if tipo != "van" else (.1,)):
            xh = pb0 - L * t - .28; zh = est[len(est) // 2][2] - .08
            box(nome + "_Macaneta", (.14, .03, .035), (xh, sup_y(xh, zh, lado) + lado * .012, zh), M["plast"], col, R, bevel=.01)
    # interior: painel, bancos, volante (lado esquerdo = +Y)
    zc = est[len(est) // 2][2]                              # cintura
    xb = pb0 - L * .12
    box(nome + "_Painel", (.35, hw_max * 1.7, .25), (pb1 - .25, 0, zc - .04), M["interior"], col, R, bevel=.05)
    for sy in (-1, 1):
        box(nome + "_Banco", (.5, .5, .1), (xb, sy * hw_max * .42, zc - .42), M["interior"], col, R, bevel=.04)
        box(nome + "_Encosto", (.12, .48, .62), (xb - .3, sy * hw_max * .42, zc - .08), M["interior"], col, R, rot=(0, .2, 0), bevel=.04)
    if tipo != "van":
        box(nome + "_Banco_Tras", (.5, hw_max * 1.5, .1), (xb - .95, 0, zc - .4), M["interior"], col, R, bevel=.04)
        box(nome + "_Encosto_Tras", (.12, hw_max * 1.5, .55), (xb - 1.25, 0, zc - .1), M["interior"], col, R, rot=(0, .2, 0), bevel=.04)
    cyl(nome + "_Volante", .18, .18, .028, (pb1 - .52, hw_max * .42, zc + .03), M["preto"], col, R, rot=(0, -1.15, 0), seg=20)
    R["banco"] = [xb, hw_max * .42, zc - .37]
    box(nome + "_Assoalho", (comp * .8, hw_max * 1.6, .04), (0, 0, est[len(est) // 2][1] + .04), M["preto"], col, R)
    # placas (padrao Mercosul, combinacao ficticia)
    for ponta, x0, z0 in ((1, xfr + .035, est[0][1] + .06), (-1, sup_x(0, zl - .28, -1) - .012, zl - .28)):
        box(nome + "_Placa", (.01, .4, .13), (x0, 0, z0), M["placa"], col, R)
        box(nome + "_Placa_Faixa", (.012, .4, .03), (x0 + ponta * .001, 0, z0 + .05), M["placa_azul"], col, R)
        texto(nome + "_Placa_Texto", placa, .065, (x0 + ponta * .007, 0, z0 - .012), "+x" if ponta > 0 else "-x", M["texto_pr"], col, R)
    return R, sup_y, sup_x, corpo

def giroflex(R, col, x, z, larg=1.1):
    box("Giroflex_Base", (.32, larg, .05), (x, 0, z), M["preto"], col, R, bevel=.015)
    n = 6; w = larg / n
    for k in range(n):
        y = -larg / 2 + w * (k + .5)
        box("Giroflex_Lente_%d" % (k + 1), (.28, w * .92, .09), (x, y, z + .07), M["giro_verm"] if k < 3 else M["giro_azul"], col, R, bevel=.022)
    luz("Giroflex_Luz_Vermelha", "POINT", 0, "#ff1a10", (x, -.35, z + .2), col, R)
    luz("Giroflex_Luz_Azul", "POINT", 0, "#2050ff", (x, .35, z + .2), col, R)

# ---- guincho plataforma
def guincho(pos):
    R = vazio("Guincho", pos, C_VEIC); c = C_VEIC; n = "Guincho"
    box(n + "_Chassi", (7.6, .9, .22), (-.3, 0, .72), M["preto"], c, R)
    box(n + "_Cabine", (1.9, 2.25, 1.75), (2.75, 0, 1.75), M["pint_guincho"], c, R, bevel=.14, seg=3)
    box(n + "_Para_Brisa", (.05, 1.95, .8), (3.69, 0, 2.08), M["vidro"], c, R, rot=(0, -.12, 0))
    for sy in (-1, 1):
        box(n + "_Vidro_Porta", (.85, .04, .62), (2.95, sy * 1.115, 2.12), M["vidro"], c, R)
        box(n + "_Faixa_Cabine", (1.75, .012, .2), (2.75, sy * 1.13, 1.35), M["azul_claro"], c, R)
        box(n + "_Retrovisor", (.06, .18, .34), (3.5, sy * 1.32, 2.15), M["plast"], c, R, bevel=.02)
        box(n + "_Farol", (.06, .34, .16), (3.71, sy * .8, 1.12), M["farol"], c, R, bevel=.02)
        box(n + "_Lanterna", (.05, .25, .1), (-4.12, sy * .95, .82), M["lanterna"], c, R)
        box(n + "_Guarda_Lateral", (5.9, .05, .12), (-1.15, sy * 1.2, 1.1), M["plataforma"], c, R)
        box(n + "_Trilho_Chapa", (5.7, .55, .012), (-1.15, sy * .78, 1.052), M["metal"], c, R)
        box(n + "_Caixa_Ferramentas", (1.0, .35, .4), (.9, sy * .95, .72), M["pint_guincho"], c, R, bevel=.03)
    box(n + "_Parachoque", (.22, 2.3, .34), (3.68, 0, .72), M["plast"], c, R, bevel=.06)
    box(n + "_Grade", (.05, 1.3, .3), (3.71, 0, 1.2), M["preto_b"], c, R, bevel=.03)
    box(n + "_Plataforma", (5.9, 2.4, .1), (-1.15, 0, 1.0), M["plataforma"], c, R)
    box(n + "_Protetor_Cabine", (.08, 2.3, 1.2), (1.72, 0, 1.65), M["plataforma"], c, R)
    box(n + "_Guincho_Tambor", (.4, .5, .3), (1.4, 0, 1.2), M["preto"], c, R, bevel=.04)
    box(n + "_Barra_Sinalizador", (.25, 1.3, .1), (2.6, 0, 2.7), M["ambar"], c, R, bevel=.03)
    box(n + "_Placa", (.01, .4, .13), (3.8, 0, .72), M["placa"], c, R)
    texto(n + "_Placa_Texto", "GUI5N26", .065, (3.807, 0, .71), "+x", M["texto_pr"], c, R)
    PN = [(.3, -.14), (.42, -.15), (.47, -.11), (.48, -.05), (.48, .05), (.47, .11), (.42, .15), (.3, .14)]
    AR = [(0, .1), (.1, .1), (.12, .06), (.28, .06), (.3, .12), (.3, -.12)]
    for x, duplo in ((2.6, False), (-2.3, True)):
        for sy in (-1, 1):
            for d in ((0, -.33) if duplo else (0,)):
                g = vazio(n + "_Roda", (x, sy * (1.02 + d), .48), c, 0, R); g.rotation_euler = (-sy * PI / 2, 0, 0)
                torno(n + "_Pneu", PN, M["pneu"], c, g, seg=24); torno(n + "_Aro", AR, M["aro_aco"], c, g, seg=16)
    for sy in (-1, 1):
        texto(n + "_Texto", "REBOQUE", .16, (2.75, sy * 1.137, 1.05), "+y" if sy > 0 else "-y", M["texto_az"], c, R)
    return R

# ---- veiculos de modelos prontos (modelos/carros/*.glb - Sketchfab, Comrade1280, CC-BY 4.0; ver modelos/CREDITOS.md)
#      Se o .glb faltar, cai no veiculo gerado por codigo (funcao veiculo, acima).
CARROS = os.path.join(AQUI, "modelos", "carros")

def repintar(img, cor, nome):
    """Troca a cor da pintura (pixels saturados da textura) mantendo sombras, frisos e detalhes."""
    w, h = img.size; px = np.empty(w * h * 4, np.float32); img.pixels.foreach_get(px); px = px.reshape(-1, 4)
    rgb = px[:, :3]; mx = rgb.max(1); mn = rgb.min(1); sat = (mx - mn) / np.maximum(mx, 1e-4)
    m = (sat > .3) & (mx > .12)
    if m.sum() < 100: return img
    ref = np.median(mx[m]); k = np.clip(mx[m] / ref, 0, 1.6)[:, None]
    rgb[m] = np.clip(np.array(lin(hx(cor)) if False else hx(cor), np.float32)[None, :] * k, 0, 1)
    novo = bpy.data.images.new(nome, w, h, alpha=True); novo.pixels.foreach_set(px.ravel()); novo.pack()
    return novo

def carro_modelo(nome, col, arquivo, pos, rz, cor=None, tirar=(), janela_aberta=False, interior=False, porta=None):
    """Importa modelos/carros/<arquivo>.glb com a frente para +X. Devolve (raiz, sup_y, sup_x, info) ou None se faltar."""
    caminho = os.path.join(CARROS, arquivo + ".glb")
    if not os.path.exists(caminho): return None
    antes = set(bpy.data.objects)
    bpy.ops.import_scene.gltf(filepath=caminho)
    novos = [o for o in bpy.data.objects if o not in antes]
    R = next(o for o in novos if o.parent is None); R.name = nome
    for o in novos:
        for c in list(o.users_collection): c.objects.unlink(o)
        col.objects.link(o)
        if o is not R: o.name = nome + "_" + o.name.split(".")[0].replace("Roda_", "Roda_")
    corpo = next(o for o in novos if o.type == "MESH" and "Carroceria" in o.name)
    feitos = {}
    for i, s in enumerate(corpo.material_slots):          # materiais proprios deste carro (UV do modelo e preservada no pipeline)
        m = s.material.copy(); m.name = "Modelo_%s_%s" % (nome, s.material.name.split(".")[0]); s.material = m
        b = next((n for n in m.node_tree.nodes if n.type == "BSDF_PRINCIPLED"), None)
        tex = next((n for n in m.node_tree.nodes if n.type == "TEX_IMAGE" and n.outputs["Color"].is_linked and any(l.to_socket.name == "Base Color" for l in n.outputs["Color"].links)), None)
        nm = m.name.lower()
        if cor and tex and tex.image and not any(k in nm for k in ("glass", "optic", "decal")):
            tex.image = feitos.setdefault(tex.image.name, repintar(tex.image, cor, "pintura_%s_%s" % (nome, tex.image.name)))
        if "glass" in nm and b:
            for l in list(b.inputs["Alpha"].links): m.node_tree.links.remove(l)
            for l in list(b.inputs["Base Color"].links): m.node_tree.links.remove(l)
            b.inputs["Base Color"].default_value = (.03, .045, .055, 1); b.inputs["Alpha"].default_value = .38 if interior else .8
            b.inputs["Roughness"].default_value = .06; b.inputs["Metallic"].default_value = 0
            for attr, val in (("surface_render_method", "BLENDED"), ("blend_method", "BLEND")):
                try: setattr(m, attr, val)
                except Exception: pass
        if interior: m.use_backface_culling = False
    me = corpo.data
    bm = bmesh.new(); bm.from_mesh(me)
    nomes = [s.material.name.lower() for s in corpo.material_slots]
    apagar = [f for f in bm.faces if any(k in nomes[f.material_index] for k in tirar)]
    vidro = [f for f in bm.faces if "glass" in nomes[f.material_index]]
    esq = [f for f in vidro if f.normal.y > .55 and abs(f.normal.z) < .6]          # vidros laterais do lado do motorista (+Y)
    info = {}
    if esq:
        xs = [f.calc_center_median().x for f in esq]; meio = (min(xs) + max(xs)) / 2
        frente = [f for f in esq if f.calc_center_median().x > meio]
        c = sum((f.calc_center_median() for f in frente), Vector()) / len(frente)
        info["janela"] = c.copy()
        info["jx"] = (min(v.co.x for f in frente for v in f.verts), max(v.co.x for f in frente for v in f.verts))
        if janela_aberta: apagar += frente
    if apagar: bmesh.ops.delete(bm, geom=list(set(apagar)), context="FACES")
    tem_porta = False
    if porta and "jx" in info:
        # porta do motorista: recorta a lateral esquerda entre a coluna da frente e a do meio, da soleira ao teto,
        # e separa numa peca propria com a origem na dobradica (o site gira a peca para abrir)
        hw_ = max(v.co.y for v in bm.verts)
        xd1, zb_ = info["jx"][1] + porta[1], porta[2]; xd0 = xd1 - porta[0]       # porta = (comprimento, folga a frente da janela, altura da soleira)
        for co, no in (((xd0, 0, 0), (1, 0, 0)), ((xd1, 0, 0), (1, 0, 0)), ((0, 0, zb_), (0, 0, 1))):
            fs = [f for f in bm.faces if f.calc_center_median().y > 0]
            geom = list({v for f in fs for v in f.verts}) + list({e for f in fs for e in f.edges}) + fs
            bmesh.ops.bisect_plane(bm, geom=geom, plane_co=co, plane_no=no, dist=1e-4)
        for f in bm.faces:
            c = f.calc_center_median()
            f.select = bool(c.y > hw_ * .45 and xd0 < c.x < xd1 and c.z > zb_ and f.normal.z < .8 and f.normal.y > -.3)
        tem_porta = any(f.select for f in bm.faces)
        info["dobradica"] = Vector((xd1, hw_ - .04, zb_ + .35))
    bm.to_mesh(me); bm.free()
    if tem_porta:
        mp = me.copy(); mp.name = nome + "_Porta"
        for malha_, manter_sel in ((me, False), (mp, True)):
            b2 = bmesh.new(); b2.from_mesh(malha_)
            bmesh.ops.delete(b2, geom=[f for f in b2.faces if f.select != manter_sel], context="FACES")
            if manter_sel: bmesh.ops.translate(b2, verts=b2.verts, vec=-info["dobradica"])
            b2.to_mesh(malha_); b2.free()
        P = bpy.data.objects.new(nome + "_Porta", mp); col.objects.link(P); P.parent = R; P.location = info["dobradica"]
        for p_ in mp.polygons: p_.use_smooth = True
    R.location = pos; R.rotation_euler = (0, 0, rz)
    bpy.context.view_layer.update()
    pts = [Vector(c) for c in corpo.bound_box]
    hw = max(abs(p.y) for p in pts); comp = max(p.x for p in pts) - min(p.x for p in pts); alt = max(p.z for p in pts)
    info.update(hw=hw, comp=comp, alt=alt)
    if interior and "janela" in info:                     # o modelo e oco: bancos, painel e assoalho simples
        j = info["janela"]; xb = j.x - .18; zb = j.z - .62; yb = hw * .45
        for sy in (-1, 1):
            box(nome + "_Banco", (.5, .48, .1), (xb, sy * yb, zb), M["interior"], col, R, bevel=.04)
            box(nome + "_Encosto", (.12, .46, .6), (xb - .3, sy * yb, zb + .34), M["interior"], col, R, rot=(0, .2, 0), bevel=.04)
        box(nome + "_Banco_Tras", (.5, hw * 1.5, .1), (xb - .95, 0, zb + .02), M["interior"], col, R, bevel=.04)
        box(nome + "_Encosto_Tras", (.12, hw * 1.5, .5), (xb - 1.22, 0, zb + .32), M["interior"], col, R, rot=(0, .2, 0), bevel=.04)
        box(nome + "_Painel", (.3, hw * 1.55, .22), (xb + .78, 0, zb + .42), M["interior"], col, R, bevel=.05)
        cyl(nome + "_Volante", .17, .17, .026, (xb + .52, yb, zb + .47), M["preto"], col, R, rot=(0, -1.15, 0), seg=18)
        box(nome + "_Assoalho", (comp * .62, hw * 1.5, .03), (xb - .2, 0, zb - .28), M["preto"], col, R)
        info["banco"] = [xb, yb, zb + .05]
    ev = corpo.evaluated_get(bpy.context.evaluated_depsgraph_get())
    def sup_y(x, z, lado):
        ok, lc, _, _ = ev.ray_cast(Vector((x, lado * 3.0, z)), Vector((0, -lado, 0)))
        return lc.y if ok else lado * hw
    def sup_x(y, z, ponta):
        ok, lc, _, _ = ev.ray_cast(Vector((ponta * 6.0, y, z)), Vector((-ponta, 0, 0)))
        return lc.x if ok else ponta * comp / 2
    return R, sup_y, sup_x, info

def faixa_lateral(nome, R, col, sup_y, x0, x1, z0, z1, m, n=24):
    """Faixa pintada que acompanha a lateral do carro (dos dois lados)."""
    for lado in (1, -1):
        vs, fs = [], []
        for i in range(n + 1):
            x = x0 + (x1 - x0) * i / n
            for z in (z0, z1): vs.append((x, sup_y(x, z, lado) + lado * .006, z))
        for i in range(n): fs.append((2 * i, 2 * i + 2, 2 * i + 3, 2 * i + 1))
        malha(nome, vs, fs, m, col, R)

# ---- viatura da Policia Militar (apoio a seguranca): perua repintada de branco, faixa azul, giroflex
r = carro_modelo("Viatura_PM", C_VEIC, "perua", (9.6, 5.45, 0), 0, cor="#eceded")
if r:
    VTR, sy_, sx_, inf = r
    giroflex(VTR, C_VEIC, -.25, inf["alt"] + .03, larg=1.05)
    faixa_lateral("Viatura_Faixa_Azul", VTR, C_VEIC, sy_, -1.85, 1.55, .5, .66, M["faixa_pm"])
    for lado in (1, -1):
        v = "+y" if lado > 0 else "-y"
        texto("Adesivo_Policia_Militar", "POLÍCIA MILITAR", .085, (-.15, sy_(-.15, .82, lado) + lado * .008, .82), v, M["texto_az"], C_VEIC, VTR)
        texto("Adesivo_190", "190", .12, (-1.55, sy_(-1.55, .84, lado) + lado * .008, .84), v, M["texto_az"], C_VEIC, VTR)
        cyl("Brasao_Imagem", .09, .09, .004, (.95, sy_(.95, .82, lado) + lado * .006, .82), M["brasao"], C_VEIC, VTR, rot=(PI / 2, 0, 0), seg=28)
else:
    VTR, sy_, sx_, _ = veiculo("Viatura_PM", C_VEIC, (9.6, 5.45, 0), 0, EST_SUV, M["pint_pm"], M["faixa_pm"], "suv", placa="RJP0M19")
    giroflex(VTR, C_VEIC, -.25, 1.72)

# ---- van de apoio: van repintada de branco, sem o adesivo original, com LEI SECA
r = carro_modelo("Van_Apoio", C_VEIC, "van", (0.4, 5.5, 0), 0, cor="#eeefef", tirar=("decal",))
if r:
    VAN, sy_, sx_, inf = r
    faixa_lateral("Van_Faixa_Azul", VAN, C_VEIC, sy_, -2.45, 1.3, .62, .8, M["azul_claro"])
    if LOGO: logo_lateral("Van_Logo", VAN, C_VEIC, sy_, -.95, 1.33, 2.5)
    for lado in (1, -1):
        v = "+y" if lado > 0 else "-y"
        if not LOGO: texto("Van_Texto_Lei_Seca", "LEI SECA", .36, (-.95, sy_(-.95, 1.3, lado) + lado * .01, 1.3), v, M["texto_az"], C_VEIC, VAN)
        if not LOGO: texto("Van_Texto_Sub", "OPERAÇÃO DE FISCALIZAÇÃO", .085, (-.95, sy_(-.95, 1.0, lado) + lado * .01, 1.0), v, M["texto_az"], C_VEIC, VAN)
else:
    veiculo("Van_Apoio", C_VEIC, (0.4, 5.5, 0), 0, EST_VAN, M["pint_van"], M["azul_claro"], "van", aro=M["aro_aco"], placa="LSC4E26")

# ---- guincho plataforma
r = carro_modelo("Guincho", C_VEIC, "guincho", (20.2, 5.4, 0), 0)
if r:
    scene["ls_guincho_luz"] = [20.2 + r[3]["comp"] / 2 - 1.05, 5.4, r[3]["alt"] + .06]
else:
    guincho((20.2, 5.4, 0))

# ---- carro abordado (para no ponto de abordagem; janela do motorista aberta) e carro na regularizacao
r = carro_modelo("Carro_Abordado", C_ABORD, "hatch", (-7.0, 1.9, 0), 0, cor="#9a9da3", janela_aberta=True, interior=True, porta=(1.1, .2, .3))
if r:
    ABORD = r[0]; ABORD["banco"] = r[3].get("banco", [.1, .36, .35])
else:
    ABORD, _, _, corpo_ab = veiculo("Carro_Abordado", C_ABORD, (-7.0, 1.9, 0), 0, EST_HATCH, M["pint_cinza"], None, "hatch", janela_aberta=True, placa="KXR3B47")
if not carro_modelo("Carro_Regularizacao", C_REG, "seda", (13.2, 1.75, 0), .04, cor="#e9e9e6"):
    veiculo("Carro_Regularizacao", C_REG, (13.2, 1.75, 0), .04, EST_HATCH, M["pint_branca"], None, "hatch", placa="LTM8F02")

# ================================================================== 7. EQUIPAMENTOS (interativos)
# mesa de equipamentos ao lado do ponto de abordagem
MX, MY = -4.2, 4.35
mesa("Mesa_Equipamentos", MX, MY, 0, (1.5, .7), toalha=M["azul"])
ZT = .758
mal = vazio("I_Maleta_Etilometro", (MX - .42, MY + .05, ZT), C_INT, .12)
box("I_Maleta_Base", (.42, .32, .1), (0, 0, .05), M["maleta"], C_INT, mal, bevel=.015)
box("I_Maleta_Espuma", (.38, .28, .02), (0, 0, .095), M["espuma"], C_INT, mal)
box("I_Maleta_Tampa", (.42, .05, .32), (0, .185, .2), M["maleta"], C_INT, mal, rot=(-.25, 0, 0), bevel=.015)
box("I_Maleta_Impressora", (.12, .09, .05), (-.1, .06, .125), M["preto"], C_INT, mal, bevel=.01)

eti = vazio("I_Etilometro", (MX + .02, MY - .08, ZT), C_INT, -.3)
box("I_Etilometro_Corpo", (.075, .15, .04), (0, 0, .02), M["preto"], C_INT, eti, bevel=.012, seg=3)
box("I_Etilometro_Visor", (.055, .045, .004), (0, .03, .041), M["tela_verde"], C_INT, eti)
for kx in (-.02, 0, .02):
    cyl("I_Etilometro_Botao", .007, .007, .004, (kx, -.035, .042), M["azul_claro"], C_INT, eti, seg=10)
cyl("I_Etilometro_Encaixe", .011, .011, .03, (0, .088, .022), M["metal"], C_INT, eti, rot=(PI / 2, 0, 0), seg=12)

cx = vazio("I_Caixa_Bocais", (MX + .38, MY + .08, ZT), C_INT, .2)
box("I_Caixa_Bocais_Caixa", (.22, .16, .07), (0, 0, .035), M["branco"], C_INT, cx, bevel=.008)
for k in range(8):
    cyl("I_Bocal_Embalado", .009, .009, .1, (-.08 + (k % 4) * .053, -.035 + (k // 4) * .07, .078), M["bocal"], C_INT, cx, rot=(PI / 2, 0, rnd.uniform(-.2, .2)), seg=8)
texto("I_Caixa_Bocais_Texto", "BOCAIS DESCARTÁVEIS", .017, (0, -.082, .035), "-y", M["texto_az"], C_INT, cx)

tab = vazio("I_Tablet", (MX + .2, MY - .2, ZT), C_INT, .35)
box("I_Tablet_Corpo", (.25, .17, .01), (0, 0, .005), M["preto"], C_INT, tab, bevel=.004)
box("I_Tablet_Tela", (.225, .15, .002), (0, 0, .0105), M["tela"], C_INT, tab)

lix = vazio("I_Lixeira_Bocais", (MX + 1.05, MY - .1, 0), C_INT)
torno("I_Lixeira_Corpo", [(.0, 0), (.13, 0), (.16, .38), (.15, .38), (.12, .02)], M["azul"], C_INT, lix, seg=16)

# mesa de teste / regularizacao (ao lado do segundo carro)
mesa("Mesa_Teste", 8.4, 3.0, .15)
cadeira("Cadeira_Teste_0", 7.5, 3.6, .5, C_BLITZ); cadeira("Cadeira_Teste_1", 7.3, 2.6, 1.3, C_BLITZ)
box("Maleta_Teste", (.4, .3, .11), (8.25, 3.05, .8), M["maleta"], C_BLITZ, bevel=.015)
box("Maleta_Chao", (.45, .16, .34), (7.75, 2.5, .17), M["maleta"], C_BLITZ, bevel=.02)

# ================================================================== 8. CAMERAS, CEU, RENDER
def camera(nome, pos, alvo, lente=24):
    cd = bpy.data.cameras.new(nome); cd.lens = lente; cd.clip_end = 400
    ob = bpy.data.objects.new(nome, cd); C_LUZ.objects.link(ob); ob.location = pos
    ob.rotation_euler = (Vector(alvo) - Vector(pos)).to_track_quat("-Z", "Y").to_euler()
    return ob
camera("Camera_Abordagem", (-4.6, 5.9, 1.65), (-7.6, 1.6, 1.0), 20)
camera("Camera_Chegada", (-27.0, 2.6, 1.65), (-10, 3.0, 1.2), 22)
camera("Camera_Tenda", (-13.5, 1.2, 1.65), (-10, 6.0, 1.6), 20)
camera("Camera_Teste", (5.0, 0.9, 1.65), (11, 3.6, 1.0), 20)
camera("Camera_Apoio", (-4.5, -1.2, 1.7), (-3.0, 6.5, 1.9), 20)
camera("Camera_Aerea", (-1.0, -9.5, 17.0), (0.0, 3.2, 0), 15)
scene.camera = bpy.data.objects["Camera_Aerea"]

world = bpy.data.worlds.get("World") or bpy.data.worlds.new("World"); scene.world = world
bg = world.node_tree.nodes.get("Background")
if bg:
    bg.inputs["Color"].default_value = (*lin(hx("#1b2640")), 1); bg.inputs["Strength"].default_value = .22
scene.unit_settings.system = "METRIC"
scene.render.resolution_x, scene.render.resolution_y = 1920, 1080
scene.render.engine = "CYCLES"; scene.cycles.samples = 128; scene.cycles.use_denoising = True
for attr, val in (("view_transform", "AgX"), ("look", "AgX - Medium High Contrast")):
    try: setattr(scene.view_settings, attr, val)
    except Exception: pass
scene.view_settings.exposure = 0.0

# pontos usados pelo site (o pipeline three.js le estas propriedades e grava em cena.json)
scene["ls_parada"] = [-7.0, 1.9, 0.0]
scene["ls_torres"] = [v for t in TORRES for v in t]
scene["ls_mesa_equip"] = [MX, MY, ZT]
scene["ls_banco"] = list(ABORD["banco"])

bpy.ops.wm.save_as_mainfile(filepath=os.path.join(AQUI, "blitz_lei_seca.blend"))
tris = 0
dg = bpy.context.evaluated_depsgraph_get()
for o in scene.objects:
    if o.type == "MESH" and not o.hide_render:
        e = o.evaluated_get(dg); m = e.to_mesh(); tris += sum(len(p.vertices) - 2 for p in m.polygons); e.to_mesh_clear()
say("cena criada: %d objetos, ~%d triangulos -> blitz_lei_seca.blend" % (len(bpy.data.objects), tris))
