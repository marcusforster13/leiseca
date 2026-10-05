"""
Operacao Lei Seca - integra modelos feitos a mao (.glb) na CENA PRINCIPAL.

Como usar:
  1. Exporte o modelo do Blender como .glb, MANTENDO a mesma posicao da cena (como foi feito com os livros).
  2. Coloque o .glb em 01_Cena_Render_Cycles/modelos/
  3. Registre em modelos/modelos.json:  { "arquivo.glb": { "substitui": "NomeDoObjetoRaiz", "colecao": "02_Sala" } }
  4. Rode:  blender -b blitz_lei_seca.blend --python integrar_modelos.py
     (ou pelo atualizar_tudo.ps1, que ja chama este script antes de gerar as versoes VR e three.js)

O que o script faz:
  - backup automatico em backup/ antes de alterar
  - apaga o objeto antigo (e todos os filhos) indicado em "substitui"
  - importa o .glb no lugar, na colecao indicada
  - religa materiais pelo nome (ex.: "Madeira_Freijo.001" -> "Madeira_Freijo"), entao as texturas CC0 da cena valem
  - so reintegra se o .glb mudou (guarda a data do arquivo no proprio .blend)
"""
import bpy, os, json, time, shutil, re

try:
    AQUI = os.path.dirname(os.path.abspath(__file__))
except NameError:
    AQUI = os.path.join(os.path.expanduser("~"), "Downloads", "leiseca", "01_Cena_Render_Cycles")
MOD = os.path.join(AQUI, "modelos")
CFG = os.path.join(MOD, "modelos.json")

def say(m):
    print("[MODELOS] " + m)

def apagar_hierarquia(ob):
    for c in list(ob.children):
        apagar_hierarquia(c)
    bpy.data.objects.remove(ob, do_unlink=True)

def base(nome):
    return re.sub(r"\.\d{3}$", "", nome)

if not os.path.exists(CFG):
    say("nenhum modelos.json encontrado; nada a fazer")
else:
    cfg = json.load(open(CFG, encoding="utf-8"))
    estado = bpy.context.scene.get("modelos_integrados", "{}")
    estado = json.loads(estado) if isinstance(estado, str) else {}
    pendentes = []
    for arq, info in cfg.items():
        caminho = os.path.join(MOD, arq)
        if not os.path.exists(caminho):
            say("AVISO: %s nao encontrado" % arq); continue
        mtime = os.path.getmtime(caminho)
        if estado.get(arq) == mtime and "--forcar" not in os.sys.argv:
            say("%s ja integrado (sem mudancas)" % arq); continue
        pendentes.append((arq, caminho, mtime, info))

    if pendentes and bpy.data.filepath:
        bk = os.path.join(AQUI, "backup")
        os.makedirs(bk, exist_ok=True)
        destino = os.path.join(bk, "blitz_lei_seca_%s.blend" % time.strftime("%Y%m%d_%H%M%S"))
        shutil.copy2(bpy.data.filepath, destino)
        say("backup: %s" % os.path.basename(destino))

    for arq, caminho, mtime, info in pendentes:
        nomes = info["substitui"] if isinstance(info["substitui"], list) else [info["substitui"]]
        for nome in nomes:                          # aceita um nome ou uma lista de nomes
            alvo = bpy.data.objects.get(nome)
            if alvo:
                apagar_hierarquia(alvo)
        antes = set(bpy.data.objects)
        mats_antes = set(bpy.data.materials)
        bpy.ops.import_scene.gltf(filepath=caminho)
        novos = [o for o in bpy.data.objects if o not in antes]
        col = bpy.data.collections.get(info.get("colecao", "")) or bpy.context.scene.collection
        religados = 0
        for o in novos:
            for c in list(o.users_collection):
                c.objects.unlink(o)
            col.objects.link(o)
            o["modelo_usuario"] = arq          # os scripts de detalhamento nao mexem em modelos feitos a mao
            for slot in o.material_slots:
                m = slot.material
                if m and m not in mats_antes:
                    existente = bpy.data.materials.get(base(m.name))
                    if existente and existente not in (m,) and existente in mats_antes:
                        slot.material = existente; religados += 1
        for m in [m for m in bpy.data.materials if m.users == 0 and m not in mats_antes]:
            bpy.data.materials.remove(m)
        estado[arq] = mtime
        say("%s -> substituiu '%s' com %d objetos em %s (%d materiais religados aos da cena)"
            % (arq, info["substitui"], len(novos), col.name, religados))

    bpy.context.scene["modelos_integrados"] = json.dumps(estado)
    if pendentes and bpy.app.background:
        bpy.ops.wm.save_mainfile()
        say("cena principal salva")
