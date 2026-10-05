"""
Operacao Lei Seca - arvores de rua realistas (substitui as copas de "bolota").

Cada arvore (porte de oiti / amendoeira, comuns nas calcadas do Rio) vira:
  - tronco com casca (textura CC0), levemente torto, com raizes aparentes na base
  - 3 a 4 galhos principais que se abrem e se dividem em galhos finos
  - copa de centenas de raminhos de folhas (cartoes com transparencia recortada) presos nas pontas dos galhos,
    mais um miolo escuro que da volume e nao deixa ver o ceu atraves da copa
Idempotente: reconstroi a partir dos canteiros (objetos Arvore_*_Canteiro).

Uso:  blender -b blitz_lei_seca.blend --python arvores.py
"""
import bpy, bmesh, math, random, zlib
import numpy as np
from mathutils import Vector, Matrix, noise

def say(m):
    print("[ARVORE] " + m)

# ------------------------------------------------------------------ textura: 4 raminhos (atlas 2x2)
def textura_raminhos(S=1024, semente=7):
    rnd = np.random.default_rng(semente)
    img = np.zeros((S, S, 4), np.float32)
    C = S // 2
    yy, xx = np.mgrid[0:C, 0:C].astype(np.float32)
    verdes = np.array([[38, 78, 30], [52, 96, 34], [70, 112, 40], [44, 88, 42], [86, 128, 48]], np.float32) / 255
    for cel in range(4):
        cx0, cy0 = (cel % 2) * C, (cel // 2) * C
        cor = np.zeros((C, C, 3), np.float32); alfa = np.zeros((C, C), np.float32)
        # galhos: 2 ou 3 hastes saindo da base, levemente curvas
        for h in range(rnd.integers(2, 4)):
            ang0 = rnd.uniform(-.45, .45); curva = rnd.uniform(-.5, .5)
            px, py = C / 2 + rnd.uniform(-20, 20), C - 4.0
            comp = rnd.uniform(.75, .95) * C
            pts = []
            for k in range(60):
                t = k / 59; a = ang0 + curva * t
                px += math.sin(a) * comp / 60; py -= math.cos(a) * comp / 60
                pts.append((px, py, a, t))
            for (px_, py_, a, t) in pts:          # haste fina
                d = np.hypot(xx - px_, yy - py_) < 2.2 - 1.2 * t
                cor[d] = (.20, .24, .10); alfa[d] = 1
            # folhas alternadas ao longo da haste (menores na ponta)
            for k in range(rnd.integers(9, 14)):
                t = .12 + .88 * k / 13
                px_, py_, a, _ = pts[min(59, int(t * 59))]
                lado = 1 if k % 2 else -1
                ang = a + lado * rnd.uniform(.55, 1.05)
                L = rnd.uniform(.17, .24) * C * (1.15 - .45 * t); W = L * rnd.uniform(.36, .48)
                ux, uy = math.sin(ang), -math.cos(ang)            # eixo da folha (da base para a ponta)
                dx, dy = xx - px_, yy - py_
                u = dx * ux + dy * uy; v = -dx * uy + dy * ux
                s = np.clip(u / L, 0, 1)
                larg = W / 2 * np.power(np.sin(np.pi * np.clip(s * .92 + .04, 0, 1)), .75)
                dentro = (u > 0) & (u < L) & (np.abs(v) < larg)
                base = verdes[rnd.integers(len(verdes))] * rnd.uniform(.85, 1.1)
                tom = base * (.78 + .32 * s[..., None]) * (1 - .25 * (np.abs(v) / (larg + 1e-3))[..., None])
                nerv = dentro & (np.abs(v) < 1.3)
                tom = np.where(nerv[..., None], base * 1.35, tom)
                cor[dentro] = tom[dentro]; alfa[dentro] = 1
        cor *= (1 + .08 * rnd.standard_normal((C, C, 1))).astype(np.float32)
        img[cy0:cy0 + C, cx0:cx0 + C, :3] = np.clip(cor, 0, 1); img[cy0:cy0 + C, cx0:cx0 + C, 3] = alfa
    # "sangra" a cor para os pixels transparentes vizinhos (evita borda escura no mipmap)
    for _ in range(4):
        vaz = img[..., 3] == 0
        viz = np.maximum.reduce([np.roll(img[..., :3], s, ax) for s in (1, -1) for ax in (0, 1)])
        img[..., :3] = np.where(vaz[..., None], viz, img[..., :3])
    return img

def imagem(nome, arr):
    img = bpy.data.images.get(nome)
    if img: bpy.data.images.remove(img)
    h, w, _ = arr.shape
    img = bpy.data.images.new(nome, w, h, alpha=True)
    img.pixels.foreach_set(np.flipud(arr).ravel()); img.pack()
    return img


def material_folha():
    m = bpy.data.materials.get("Folha_Arvore") or bpy.data.materials.new("Folha_Arvore")
    nt = m.node_tree; nt.nodes.clear()
    out = nt.nodes.new("ShaderNodeOutputMaterial"); b = nt.nodes.new("ShaderNodeBsdfPrincipled")
    t = nt.nodes.new("ShaderNodeTexImage"); t.image = imagem("textura_raminhos", textura_raminhos(1024, 11))
    r = nt.nodes.new("ShaderNodeMath"); r.operation = "ROUND"
    nt.links.new(t.outputs["Color"], b.inputs["Base Color"])
    nt.links.new(t.outputs["Alpha"], r.inputs[0]); nt.links.new(r.outputs[0], b.inputs["Alpha"])
    b.inputs["Roughness"].default_value = .5
    nt.links.new(b.outputs[0], out.inputs[0])
    for attr, val in (("surface_render_method", "DITHERED"), ("blend_method", "CLIP")):
        try: setattr(m, attr, val)
        except Exception: pass
    m.use_backface_culling = False
    return m

def material_miolo():
    m = bpy.data.materials.get("Copa_Miolo") or bpy.data.materials.new("Copa_Miolo")
    b = m.node_tree.nodes.get("Principled BSDF")
    b.inputs["Base Color"].default_value = (.016, .04, .013, 1); b.inputs["Roughness"].default_value = .9
    m.diffuse_color = (.016, .04, .013, 1)
    return m

# ------------------------------------------------------------------ geometria
def tubo(bm, pts, raios, seg=8):
    """Tubo ao longo de uma linha de pontos, com raio variavel (tronco e galhos)."""
    aneis = []; ref = Vector((1, 0, 0))
    for i, p in enumerate(pts):
        d = (pts[min(i + 1, len(pts) - 1)] - pts[max(i - 1, 0)]).normalized()
        a = d.cross(ref)
        if a.length < 1e-3: a = d.cross(Vector((0, 1, 0)))
        a.normalize(); b = d.cross(a); ref = b.cross(d)
        aneis.append([bm.verts.new(p + (a * math.cos(2 * math.pi * k / seg) + b * math.sin(2 * math.pi * k / seg)) * raios[i]) for k in range(seg)])
    for i in range(len(aneis) - 1):
        for k in range(seg):
            f = bm.faces.new((aneis[i][k], aneis[i][(k + 1) % seg], aneis[i + 1][(k + 1) % seg], aneis[i + 1][k])); f.smooth = True
    bm.faces.new(aneis[-1]).smooth = True

def curva(rnd, p0, d0, comp, n, sobe=.25, torto=.22):
    """Linha de n pontos saindo de p0 na direcao d0, que entorta um pouco e tende a subir."""
    pts = [p0.copy()]; d = d0.normalized()
    for i in range(n):
        d = (d + Vector((rnd.uniform(-torto, torto), rnd.uniform(-torto, torto), sobe * rnd.uniform(.3, 1)))).normalized()
        pts.append(pts[-1] + d * comp / n)
    return pts, d

def nova_malha(nome, bm, mats, col):
    bmesh.ops.recalc_face_normals(bm, faces=[f for f in bm.faces if f.smooth])
    me = bpy.data.meshes.new(nome); bm.to_mesh(me); bm.free()
    for m in mats: me.materials.append(m)
    ob = bpy.data.objects.new(nome, me); col.objects.link(ob); ob["detalhado"] = True
    return ob

def cartao(bm, uvl, rnd, base, cima, tam):
    lado = cima.cross(Vector((rnd.gauss(0, 1), rnd.gauss(0, 1), rnd.gauss(0, 1))))
    if lado.length < 1e-3: lado = Vector((1, 0, 0))
    lado.normalize()
    cel = rnd.randrange(4); u0, v0 = (cel % 2) * .5, 1 - (cel // 2 + 1) * .5
    q = [base - lado * tam / 2, base + lado * tam / 2, base + lado * tam / 2 + cima * tam, base - lado * tam / 2 + cima * tam]
    f = bm.faces.new([bm.verts.new(p) for p in q]); f.material_index = 0; f.smooth = False
    for lp, (uu, vv) in zip(f.loops, ((0, 0), (1, 0), (1, 1), (0, 1))):
        lp[uvl].uv = (u0 + .005 + uu * .49, v0 + .005 + vv * .49)

def arvore(nome, x, y, col, m_casca, m_folha, m_miolo):
    rnd = random.Random(zlib.crc32(nome.encode()))
    H = rnd.uniform(2.5, 3.2)                              # altura do fuste (ate a primeira forquilha)
    Z0 = .15
    # ---- tronco: base alargada (raizes), fuste levemente torto
    bm = bmesh.new()
    pts, d = curva(rnd, Vector((x, y, Z0)), Vector((rnd.uniform(-.06, .06), rnd.uniform(-.06, .06), 1)), H, 7, sobe=.5, torto=.07)
    tubo(bm, pts, [.30, .21, .18, .165, .155, .15, .145, .14], 12)
    for v in bm.verts:                                     # casca irregular e raizes na base
        k = max(0, 1 - (v.co.z - Z0) / .5)
        r = Vector((v.co.x - x, v.co.y - y, 0)); ang = math.atan2(r.y, r.x)
        v.co += r * (.10 * noise.noise(v.co * 3.1) + k * .35 * max(0, math.sin(ang * 5 + x)))
    tronco = nova_malha(nome + "_Tronco", bm, [m_casca], col)
    # ---- galhos: principais + secundarios; as pontas e o meio dos galhos finos recebem folhas
    bm = bmesh.new(); topo = pts[-1]; pontos_folha = []
    n1 = rnd.randint(3, 4); a0 = rnd.uniform(0, 6.28)
    for i in range(n1 + 1):
        if i == n1: d1 = Vector((rnd.uniform(-.15, .15), rnd.uniform(-.15, .15), 1))        # lider central
        else:
            a = a0 + i * 6.283 / n1 + rnd.uniform(-.3, .3); inc = rnd.uniform(.65, .95)
            d1 = Vector((math.cos(a) * inc, math.sin(a) * inc, 1))
        L1 = rnd.uniform(1.7, 2.4) * (.8 if i == n1 else 1)
        p1, df = curva(rnd, topo - Vector((0, 0, .12)), d1, L1, 6, sobe=.16)
        tubo(bm, p1, [.115, .1, .088, .075, .064, .054, .045], 8)
        for j in range(rnd.randint(3, 4)):                 # secundarios saindo do terco final
            t = rnd.randint(3, 6); a = rnd.uniform(0, 6.28)
            d2 = (df * .6 + Vector((math.cos(a), math.sin(a), rnd.uniform(.1, .7)))).normalized()
            p2, dg = curva(rnd, p1[t], d2, rnd.uniform(1.0, 1.6), 5, sobe=.12)
            tubo(bm, p2, [.045, .038, .032, .026, .02, .014], 6)
            pontos_folha += [(p2[k], (p2[k] - p2[k - 1]).normalized(), 1.0 if k == 5 else .7) for k in (2, 3, 4, 5)]
            for q in range(2):                             # raminhos finos
                a = rnd.uniform(0, 6.28)
                d3 = (dg * .5 + Vector((math.cos(a), math.sin(a), rnd.uniform(-.1, .6)))).normalized()
                p3, dh = curva(rnd, p2[rnd.randint(2, 4)], d3, rnd.uniform(.6, 1.0), 3, sobe=.1)
                tubo(bm, p3, [.018, .014, .011, .007], 4)
                pontos_folha += [(p3[k], (p3[k] - p3[k - 1]).normalized(), 1.0) for k in (2, 3)]
        pontos_folha.append((p1[-1], df, 1.0))
    galhos = nova_malha(nome + "_Galhos", bm, [m_casca], col)
    # ---- copa: miolo escuro + raminhos de folhas
    bm = bmesh.new(); uvl = bm.loops.layers.uv.new("UVMap")      # mesmo nome das outras malhas: sobrevive a uniao por colecao
    centro = sum((p for p, _, _ in pontos_folha), Vector()) / len(pontos_folha)
    raio = max((p - centro).length for p, _, _ in pontos_folha)
    sem = Vector((rnd.uniform(0, 50), rnd.uniform(0, 50), rnd.uniform(0, 50)))
    for k in range(5):                                     # miolo: blocos irregulares no interior da copa
        c = centro + Vector((rnd.uniform(-.5, .5), rnd.uniform(-.5, .5), rnd.uniform(-.2, .5))) * raio * (.55 if k else 0)
        r = raio * (.62 if not k else rnd.uniform(.3, .42))
        g = bmesh.ops.create_icosphere(bm, subdivisions=1, radius=1)
        for v in g["verts"]:
            n = v.co.normalized()
            v.co = c + Vector((n.x, n.y, n.z * .72)) * r * (1 + .22 * noise.noise(n * 2.3 + sem + Vector((k, 0, 0))))
            for f in v.link_faces: f.material_index = 1; f.smooth = True
    n_cart = 0
    for p, d, peso in pontos_folha:                        # tufos nas pontas e ao longo dos galhos finos
        for q in range(int(rnd.randint(4, 6) * peso)):
            fora = (p - centro).normalized()
            desl = Vector((rnd.gauss(0, 1), rnd.gauss(0, 1), rnd.gauss(0, .8))) * .34
            cima = (d * .45 + fora * .5 + Vector((rnd.uniform(-.7, .7), rnd.uniform(-.7, .7), rnd.uniform(-.5, .6)))).normalized()
            tam = rnd.uniform(.62, .98)
            cartao(bm, uvl, rnd, p + desl - cima * tam * .2, cima, tam); n_cart += 1
    for q in range(110):                                   # casca externa da copa: fecha os vazios e da a silhueta
        n = Vector((rnd.gauss(0, 1), rnd.gauss(0, 1), rnd.gauss(.25, 1))).normalized()
        p = centro + Vector((n.x, n.y, n.z * .78)) * raio * rnd.uniform(.72, 1.0)
        if p.z < H * .78: continue
        cima = (n * .7 + Vector((rnd.uniform(-.6, .6), rnd.uniform(-.6, .6), rnd.uniform(-.7, .3)))).normalized()   # pontas pendem um pouco
        tam = rnd.uniform(.55, .9)
        cartao(bm, uvl, rnd, p - cima * tam * .3, cima, tam); n_cart += 1
    copa = nova_malha(nome + "_Copa", bm, [m_folha, m_miolo], col)
    return n_cart, sum(len(o.data.polygons) for o in (tronco, galhos, copa)) * 2

m_folha, m_miolo = material_folha(), material_miolo()
m_casca = bpy.data.materials.get("Tronco_Arvore")
canteiros = sorted((o for o in bpy.data.objects if o.name.startswith("Arvore_") and o.name.endswith("_Canteiro")), key=lambda o: o.name)
for o in [o for o in bpy.data.objects if o.name.startswith("Arvore_") and not o.name.endswith("_Canteiro")]:
    bpy.data.objects.remove(o, do_unlink=True)
cart = tris = 0
for c in canteiros:
    n, t = arvore(c.name[:-9], c.location.x, c.location.y, c.users_collection[0], m_casca, m_folha, m_miolo)
    cart += n; tris += t
say("%d arvores refeitas: %d raminhos de folhas, ~%d triangulos" % (len(canteiros), cart, tris))
bpy.ops.wm.save_mainfile()
