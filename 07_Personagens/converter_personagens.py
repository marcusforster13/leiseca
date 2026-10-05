"""
Operacao Lei Seca - converte os personagens do Rocketbox para o visualizador web (glTF).

Para cada papel: importa o FBX, redireciona as animacoes escolhidas (adultos "Bip01", criancas "Bip02"),
ajusta materiais (cor + relevo; cilios/cabelo com transparencia recortada), reduz as texturas
para 1024 px e exporta  04_ThreeJS/web/personagens/<papel>.glb  com as animacoes nomeadas.

Uso:  blender -b --factory-startup --python converter_personagens.py            (so o que mudou)
      blender -b --factory-startup --python converter_personagens.py -- --forcar
"""
import bpy, os, sys, json

AQUI = os.path.dirname(os.path.abspath(__file__))
RB = os.path.join(AQUI, "rocketbox")
if not os.path.isdir(RB):        # reaproveita os downloads do projeto anterior (mesma biblioteca, licenca MIT)
    RB = os.path.normpath(os.path.join(AQUI, "..", "..", "DV", "07_Personagens", "rocketbox"))
WEB = os.path.normpath(os.path.join(AQUI, "..", "04_ThreeJS", "web", "personagens"))
TMP = os.path.join(AQUI, "_texturas_web")
os.makedirs(WEB, exist_ok=True); os.makedirs(TMP, exist_ok=True)
FORCAR = "--forcar" in sys.argv

# tres condutores (sorteados a cada abordagem; quem nao dirige pode ser o passageiro)
def _anims(s):
    fala = "m_gestic_talk_neutral_01" if s == "m" else "f_gestic_talk_nervous_01"
    return {"parada": s + "_idle_neutral_01", "falando": fala, "nervoso": s + "_idle_nervous_01",
            "sentado": s + "_idle_neutral_01+sentado", "sentado_falando": fala + "+sentado_pernas",
            "sentado_nervoso": s + "_idle_nervous_01+sentado", "soprando": s + "_idle_neutral_01+soprando"}
PAPEIS = {
    "condutor_a": ("Male_Adult_01", {**_anims("m"), "irritado": "m_idle_angry_01", "andando": "m_walk_fast_01"}),
    "condutor_b": ("Female_Adult_08", _anims("f")),
    "condutor_c": ("Male_Adult_14", {**_anims("m"), "irritado": "m_idle_angry_01", "andando": "m_walk_fast_01"}),
}

REF_TPOSE = "Female_Adult_08"     # T-pose adulta usada como referencia para as criancas

def say(m):
    print("[PERSONAGENS] " + m)

def limpar():
    bpy.ops.wm.read_factory_settings(use_empty=True)

def altura_pelvis(arm):
    b = arm.data.bones.get("Bip01 Pelvis") or arm.data.bones[0]
    return (arm.matrix_world @ b.head_local).z or 1.0

def colecoes_fcurves(acao):
    """Blender 4.4+/5.x usa acoes em camadas; versoes antigas tem acao.fcurves."""
    cols = []
    if hasattr(acao, "layers") and len(acao.layers):
        for camada in acao.layers:
            for st in camada.strips:
                for cb in getattr(st, "channelbags", []):
                    cols.append(cb.fcurves)
    elif hasattr(acao, "fcurves"):
        cols.append(acao.fcurves)
    return cols

sufixo = lambda nome: nome.split(' ', 1)[1] if ' ' in nome else ''      # 'Bip01 L Thigh' -> 'L Thigh'
rot = lambda m: m.to_3x3().normalized().to_quaternion()

def repouso_mundo(esq):
    """Orientacao de cada osso no espaco do mundo, na pose de repouso (T-pose) do personagem."""
    return {sufixo(b.name): rot(esq.matrix_world @ b.matrix_local) for b in esq.data.bones}

def pose_bracos(arm, desejado, f, tgt_inv, tipo):
    """Poses de braco que o Rocketbox nao tem, aplicadas sobre a animacao base:
      maos_na_cabeca   rendicao (bracos abertos, maos sobre a cabeca)
      maos_nas_costas  algemado (bracos para tras, punhos juntos atras do quadril)
      bracos_para_cima escalando o muro (bracos esticados para cima e para a frente)
    Reorienta braco e antebraco no espaco do esqueleto; maos e dedos seguem o antebraco."""
    from mathutils import Matrix, Vector
    osso = {sufixo(b.name): b for b in arm.data.bones}
    cima = (tgt_inv.to_3x3() @ Vector((0, 0, 1))).normalized()
    cl_l, cl_r = desejado[osso["L Clavicle"].name].translation, desejado[osso["R Clavicle"].name].translation
    lado_r = (cl_r - cl_l).normalized()
    cabeca = desejado[osso["Head"].name].translation
    pelve = desejado[osso["Pelvis"].name].translation
    # frente estavel: perpendicular a linha dos ombros (o pe gira ao andar e invertia a direcao em alguns quadros);
    # o pe so decide o sentido (para a frente ou para tras)
    frente = cima.cross(lado_r).normalized()
    pe = desejado[osso["L Toe0"].name].translation - desejado[osso["L Foot"].name].translation
    pe2 = desejado[osso["R Toe0"].name].translation - desejado[osso["R Foot"].name].translation
    if frente.dot(pe + pe2) < 0: frente = -frente
    def mira(b, filho, M_pai, alvo_dir):
        # rotacao minima que leva a direcao atual do osso (ate o filho) para alvo_dir, mantendo a torcao
        M_old = desejado[b.name]
        pos = (M_pai @ (b.parent.matrix_local.inverted() @ b.matrix_local)).translation
        d_local = (b.matrix_local.inverted() @ filho.matrix_local).translation
        atual = (M_old.to_3x3() @ d_local).normalized()
        q = atual.rotation_difference(alvo_dir.normalized()) @ M_old.to_quaternion()
        M = Matrix.Translation(pos) @ q.to_matrix().to_4x4()
        desejado[b.name] = M
        base = M_pai @ b.parent.matrix_local.inverted() @ b.matrix_local
        pb = arm.pose.bones[b.name]
        pb.rotation_quaternion = (base.inverted() @ M).to_quaternion()
        pb.keyframe_insert("rotation_quaternion", frame=f)
        return M, d_local.length
    def ik_cotovelo(ombro, punho, l1, l2, polo):
        # IK de dois ossos: posicao do cotovelo para o punho chegar exatamente no alvo, dobrando para o lado do "polo"
        d = punho - ombro; dist = min(d.length, (l1 + l2) * .999); u = d.normalized()
        a = (l1 * l1 - l2 * l2 + dist * dist) / (2 * dist); h = max(0.0, l1 * l1 - a * a) ** .5
        p = (polo - u * polo.dot(u)).normalized()
        return ombro + u * a + p * h
    if tipo.startswith("sentado"):
        # sentado no banco do carro: coxas para a frente, canelas para baixo (o site abaixa o personagem ate o banco)
        for L_ in ("L", "R"):
            th, ca, ft = osso[L_ + " Thigh"], osso[L_ + " Calf"], osso[L_ + " Foot"]
            sg = -1 if L_ == "L" else 1
            M_th, _ = mira(th, ca, desejado[th.parent.name], frente * 1.0 + cima * .06 + lado_r * sg * .12)
            M_ca, _ = mira(ca, ft, M_th, -cima * .9 + frente * .42)
            dedo = osso.get(L_ + " Toe0")
            if dedo: mira(ft, dedo, M_ca, frente * 1.0 - cima * .25)
        if tipo == "sentado_pernas":
            return
    for lado, sgn in (("L", -1), ("R", 1)):
        ua, fa, hd = osso[lado + " UpperArm"], osso[lado + " Forearm"], osso[lado + " Hand"]
        lado = lado_r * sgn
        if tipo == "maos_na_cabeca":
            # punho apoiado no alto/atras da cabeca (o osso da cabeca nasce na nuca), maos se encontrando no meio
            l1 = (ua.matrix_local.inverted() @ fa.matrix_local).translation.length
            l2 = (fa.matrix_local.inverted() @ hd.matrix_local).translation.length
            ombro = (desejado[ua.parent.name] @ (ua.parent.matrix_local.inverted() @ ua.matrix_local)).translation
            punho = cabeca + cima * l1 * .58 - frente * l1 * .28 + lado * l1 * .2
            cot = ik_cotovelo(ombro, punho, l1, l2, lado * .9 - frente * .25 - cima * .2)
            M_ua, _ = mira(ua, fa, desejado[ua.parent.name], cot - ombro)
            M_fa, _ = mira(fa, hd, M_ua, punho - cot)
            dedo = osso.get(("L" if sgn < 0 else "R") + " Finger2")
            if dedo: mira(hd, dedo, M_fa, -lado * .8 - cima * .35 - frente * .15)   # dedos por cima da cabeca, para a outra mao
            continue
        if tipo == "maos_na_cabeca":                     # cotovelos abertos para os lados e um pouco para tras
            dir_braco = lado * .88 + cima * .3 - frente * .22
        elif tipo == "maos_nas_costas":
            dir_braco = -cima * .85 - frente * .42 + lado * .14
        elif tipo == "sentado":                          # maos no volante
            dir_braco = -cima * .5 + frente * .8 + lado * .12
        elif tipo == "soprando":                         # em pe, uma mao perto da boca (segurando o bocal)
            dir_braco = (-cima * .75 + frente * .55 + lado * .2) if sgn > 0 else (-cima * 1.0 + lado * .12)
        else:  # bracos_para_cima
            dir_braco = cima * .9 + frente * .35 + lado * .16
        M_ua, l_ua = mira(ua, fa, desejado[ua.parent.name], dir_braco)
        cotovelo = (M_ua @ (ua.matrix_local.inverted() @ fa.matrix_local)).translation
        if tipo == "maos_na_cabeca":                     # punhos no alto e atras da cabeca
            dir_ante = cabeca + cima * l_ua * .72 - frente * l_ua * .22 + lado * l_ua * .03 - cotovelo   # o osso da cabeca nasce na nuca: topo ~0,7 braco acima
        elif tipo == "maos_nas_costas":
            dir_ante = pelve - frente * l_ua * .5 + cima * l_ua * .05 + lado * l_ua * .04 - cotovelo
        elif tipo == "sentado":
            dir_ante = frente * .9 + cima * .3 - lado * .12
        elif tipo == "soprando":
            dir_ante = (cabeca + frente * l_ua * .45 - cima * l_ua * .1 - cotovelo) if sgn > 0 else (-cima * .9 + frente * .3)
        else:
            dir_ante = cima * .95 + frente * .22 + lado * .04
        M_fa, _ = mira(fa, hd, M_ua, dir_ante)
        if tipo == "maos_na_cabeca" and (lado_ := osso.get(("L" if sgn < 0 else "R") + " Finger2")):
            # dedos apontando para a outra mao, por cima/atras da cabeca (maos entrelacadas)
            mira(hd, lado_, M_fa, -lado * .85 + cima * .15 - frente * .25)

def redirecionar(src, arm, rest_ref, ini, fim, fator, passo=2, pose=None, no_lugar=False):
    """Passa a animacao do esqueleto src para arm. Os FBX de animacao do Rocketbox vem com a pose do 1o quadro
    gravada como repouso, entao a rotacao de cada osso e comparada com a T-pose de um personagem adulto
    (rest_ref) no espaco do mundo e aplicada sobre a T-pose deste personagem (funciona tambem nas criancas,
    cujos ossos tem outra orientacao). A pelve recebe a posicao do adulto proporcional a altura."""
    from mathutils import Matrix, Vector
    tgt_inv = arm.matrix_world.inverted()
    ordem = []
    def visita(b):
        ordem.append(b); [visita(c) for c in b.children]
    for b in arm.data.bones:
        if b.parent is None: visita(b)
    ossos_src = {sufixo(b.name): b.name for b in src.data.bones}
    pares = [(b, ossos_src.get(sufixo(b.name)) if sufixo(b.name) in rest_ref else None) for b in ordem]
    rest_tgt = repouso_mundo(arm)
    acao = bpy.data.actions.new('retarget'); arm.animation_data.action = acao
    cena = bpy.context.scene
    xy0 = None                                    # no_lugar: corrida/caminhada sem sair do lugar (o site move o personagem)
    for f in range(int(ini), int(fim) + 1, passo):
        cena.frame_set(f)
        desejado = {}
        for b, ns in pares:
            pb, s = arm.pose.bones[b.name], sufixo(b.name)
            if ns:
                delta = rot(src.matrix_world @ src.pose.bones[ns].matrix) @ rest_ref[s].inverted()
                r_arm = rot(tgt_inv) @ (delta @ rest_tgt[s])
            else:
                r_arm = rot(b.matrix_local) if not b.parent else rot(desejado[b.parent.name] @ b.parent.matrix_local.inverted() @ b.matrix_local)
            if b.parent:
                pos = (desejado[b.parent.name] @ (b.parent.matrix_local.inverted() @ b.matrix_local)).translation
            elif ns:   # pelve: posicao do adulto proporcional a altura do personagem
                w = (src.matrix_world @ src.pose.bones[ns].matrix).translation
                if no_lugar:
                    xy0 = xy0 or (w.x, w.y); w = Vector((xy0[0], xy0[1], w.z))
                pos = tgt_inv @ (w * fator)
            else:
                pos = b.matrix_local.translation
            M = Matrix.Translation(pos) @ r_arm.to_matrix().to_4x4()
            desejado[b.name] = M
            base = (desejado[b.parent.name] @ b.parent.matrix_local.inverted() @ b.matrix_local) if b.parent else b.matrix_local
            basis = base.inverted() @ M
            pb.rotation_mode = 'QUATERNION'; pb.rotation_quaternion = basis.to_quaternion()
            pb.keyframe_insert('rotation_quaternion', frame=f)
            if not b.parent:
                pb.location = basis.translation; pb.keyframe_insert('location', frame=f)
        if pose:
            pose_bracos(arm, desejado, f, tgt_inv, pose)
    arm.animation_data.action = None
    return acao

def reduzir(img, nome, dados):
    """Salva a textura em 1024 px (JPG para cor, PNG para normal) e devolve a imagem nova."""
    ext = "PNG" if dados else "JPEG"
    out = os.path.join(TMP, nome + (".png" if dados else ".jpg"))
    caminho = os.path.normpath(bpy.path.abspath(img.filepath))
    if not os.path.exists(caminho):
        return img
    img = bpy.data.images.load(caminho, check_existing=False)
    import numpy as np
    w, h = img.size
    px = np.empty(w * h * 4, np.float32); img.pixels.foreach_get(px)      # forca a leitura dos pixels
    if w > 1024:
        f = w // 1024
        px = px.reshape(h, w, 4)[::f, ::f].copy()                        # reduz 2048 -> 1024
        w, h = px.shape[1], px.shape[0]
        nova = bpy.data.images.new(nome, w, h, alpha=True)
        if dados:
            nova.colorspace_settings.name = "Non-Color"
        nova.pixels.foreach_set(px.ravel()); img = nova
    img.filepath_raw = out; img.file_format = ext
    if not dados:
        img.alpha_mode = "NONE"
    img.save()
    nova = bpy.data.images.load(out, check_existing=False)
    if dados:
        nova.colorspace_settings.name = "Non-Color"
    return nova

def arrumar_materiais(objs):
    for o in objs:
        for slot in o.material_slots:
            m = slot.material
            if not m or m.get("ok"):
                continue
            nt = m.node_tree; b = next((n for n in nt.nodes if n.type == "BSDF_PRINCIPLED"), None)
            if not b:
                continue
            for n in list(nt.nodes):        # remove texturas de brilho que nao baixamos (caminhos invalidos)
                if n.type == "TEX_IMAGE" and n.image and "specular" in n.image.filepath.lower():
                    nt.nodes.remove(n)
            for n in nt.nodes:
                if n.type == "TEX_IMAGE" and n.image:
                    dados = "normal" in n.image.filepath.lower()
                    base = os.path.splitext(os.path.basename(n.image.filepath))[0]
                    n.image = reduzir(n.image, base, dados)
            b.inputs["Roughness"].default_value = .6
            b.inputs["Metallic"].default_value = 0.0
            if "Specular IOR Level" in b.inputs:
                b.inputs["Specular IOR Level"].default_value = .35
            if "opacity" in m.name.lower():        # cilios, sobrancelhas, cabelo: transparencia recortada
                tex = next((n for n in nt.nodes if n.type == "TEX_IMAGE"), None)
                if tex:
                    rnd = nt.nodes.new("ShaderNodeMath"); rnd.operation = "ROUND"
                    nt.links.new(tex.outputs["Alpha"], rnd.inputs[0]); nt.links.new(rnd.outputs[0], b.inputs["Alpha"])
                    tex.image.alpha_mode = "STRAIGHT"
                m.use_backface_culling = False
            m["ok"] = True

manifesto = {}
for papel, (pasta, anims) in PAPEIS.items():
    fbx = os.path.join(RB, pasta, pasta + ".fbx")
    saida = os.path.join(WEB, papel + ".glb")
    fontes = [fbx] + [os.path.join(RB, "Animacoes", a.split("+")[0] + ".fbx") for a in anims.values()] + [os.path.abspath(__file__)]
    if not os.path.exists(fbx):
        say("AVISO: %s nao encontrado (baixe pelo LEIA-ME)" % fbx); continue
    if os.path.exists(saida) and (os.environ.get("SO", papel) != papel or not FORCAR and os.path.getmtime(saida) > max(os.path.getmtime(f) for f in fontes if os.path.exists(f))):   # SO=crianca: so esse papel
        say("%s ja convertido (sem mudancas)" % papel); manifesto[papel] = {"arquivo": "personagens/%s.glb" % papel, "animacoes": list(anims)}; continue
    limpar()
    bpy.ops.import_scene.fbx(filepath=fbx, use_anim=False)
    arm = next(o for o in bpy.context.scene.objects if o.type == "ARMATURE")
    malhas = [o for o in bpy.context.scene.objects if o.type == "MESH"]
    for o in [o for o in bpy.context.scene.objects if o.type == "EMPTY"]:
        bpy.data.objects.remove(o, do_unlink=True)
    # No Rocketbox a RAIZ do esqueleto guarda a altura do quadril (0,92 m em pe, 0,33 m agachado) e a direcao
    # do corpo, e cada FBX de animacao vem com a pose do 1o quadro no lugar da T-pose. Por isso a animacao e
    # redirecionada osso a osso no espaco do mundo (ver redirecionar) e gravada so nos ossos do personagem.
    REF_ADULTO = .92                                    # altura do quadril do adulto de referencia das animacoes
    raiz_z = arm.location.z                             # altura do quadril deste personagem
    fator = raiz_z / REF_ADULTO
    base_loc, base_rot = arm.location.copy(), arm.rotation_euler.copy()
    if arm.data.bones[0].name.startswith('Bip01'):
        rest_ref = repouso_mundo(arm)                   # adulto: a propria T-pose
    else:                                               # crianca (Bip02): T-pose de um adulto como referencia
        antes = set(bpy.data.objects)
        bpy.ops.import_scene.fbx(filepath=os.path.join(RB, REF_TPOSE, REF_TPOSE + '.fbx'), use_anim=False)
        novos = [o for o in bpy.data.objects if o not in antes]
        rest_ref = repouso_mundo(next(o for o in novos if o.type == 'ARMATURE'))
        for o in novos: bpy.data.objects.remove(o, do_unlink=True)
    arm.animation_data_create()
    for nome, a in anims.items():
        a, _, pose = a.partition("+")                       # "arquivo+pose" = animacao com pose ajustada
        caminho = os.path.join(RB, 'Animacoes', a + '.fbx')
        if not os.path.exists(caminho):
            say('AVISO: animacao %s nao encontrada' % a); continue
        antes = set(bpy.data.objects)
        bpy.ops.import_scene.fbx(filepath=caminho)
        novos = [o for o in bpy.data.objects if o not in antes]
        src = next((o for o in novos if o.type == 'ARMATURE'), None)
        # a acao certa e a do esqueleto (o FBX tambem traz acoes de objetos auxiliares de passos)
        acao = src.animation_data.action if src and src.animation_data and src.animation_data.action else None
        if acao:
            ini, fim = acao.frame_range[0], min(acao.frame_range[1], acao.frame_range[0] + 450)   # ate 15 s (loop)
            arm.location, arm.rotation_euler = base_loc, base_rot
            assada = redirecionar(src, arm, rest_ref, ini, fim, fator, pose=pose or None, no_lugar=a.startswith(('m_run', 'm_walk', 'f_run', 'f_walk')))
            assada.name = nome; assada.use_fake_user = True
            tr = arm.animation_data.nla_tracks.new(); tr.name = nome
            st = tr.strips.new(nome, int(ini), assada); tr.mute = True
            if hasattr(st, 'action_slot') and assada.slots:
                try: st.action_slot = assada.slots[0]
                except Exception: pass
        for o in novos: bpy.data.objects.remove(o, do_unlink=True)
    arm.animation_data.action = None
    arm.location, arm.rotation_euler = base_loc, base_rot
    arrumar_materiais(malhas)
    for o in bpy.context.scene.objects:          # exporta so o esqueleto e o corpo do personagem
        o.select_set(o == arm or o.parent == arm or o in malhas)
    for o in [o for o in bpy.context.scene.objects if not o.select_get()]:
        bpy.data.objects.remove(o, do_unlink=True)
    bpy.ops.export_scene.gltf(filepath=saida, export_format="GLB", use_selection=True, export_animations=True,
                              export_animation_mode="NLA_TRACKS", export_image_format="AUTO", export_materials="EXPORT",
                              export_draco_mesh_compression_enable=False, export_optimize_animation_size=True,
                              export_frame_step=2)
    tam = os.path.getsize(saida) / 1048576
    tris = sum(len(o.data.polygons) for o in malhas)
    say("%s (%s): %d animacoes, ~%d faces, %.1f MB -> personagens/%s.glb" % (papel, pasta, len(anims), tris, tam, papel))
    manifesto[papel] = {"arquivo": "personagens/%s.glb" % papel, "animacoes": list(anims)}

with open(os.path.join(WEB, "manifest.json"), "w", encoding="utf-8") as f:
    json.dump(manifesto, f, ensure_ascii=False, indent=1)
say("manifest.json com %d personagens" % len(manifesto))
