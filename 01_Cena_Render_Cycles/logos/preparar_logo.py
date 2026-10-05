"""
Prepara o logotipo para a cena: recorta as margens e garante fundo transparente (se a imagem vier com fundo branco,
o branco vira transparencia). Saida: logos/logo_lei_seca.png

Uso:  blender -b --factory-startup --python preparar_logo.py -- "caminho/da/imagem.webp"
"""
import bpy, os, sys
import numpy as np
AQUI = os.path.dirname(os.path.abspath(__file__))
origem = sys.argv[sys.argv.index("--") + 1]
img = bpy.data.images.load(origem)
w, h = img.size
px = np.empty(w * h * 4, np.float32); img.pixels.foreach_get(px); px = px.reshape(h, w, 4)
rgb, a = px[..., :3], px[..., 3]
if a.min() > .98:                                          # sem transparencia: o branco do fundo vira alfa
    branco = rgb.min(-1)
    a = np.clip((1 - branco) / .35, 0, 1)                  # borda suave entre a tinta e o fundo
    rgb = np.where(a[..., None] > 0, np.clip((rgb - (1 - a[..., None])) / np.maximum(a[..., None], 1e-3), 0, 1), 0)
tinta = a > .05
ys, xs = np.where(tinta)
m = 6
y0, y1, x0, x1 = max(ys.min() - m, 0), min(ys.max() + m, h - 1), max(xs.min() - m, 0), min(xs.max() + m, w - 1)
rec = np.dstack([rgb, a])[y0:y1 + 1, x0:x1 + 1]
# a cor "sangra" para os pixels transparentes (sem contorno claro no filtro de textura)
cor_media = rec[..., :3][rec[..., 3] > .5].mean(0) if (rec[..., 3] > .5).any() else np.zeros(3)
rec[..., :3] = np.where(rec[..., 3:4] > .02, rec[..., :3], cor_media * 0 + .08)
hh, ww = rec.shape[:2]
out = bpy.data.images.new("logo_lei_seca", ww, hh, alpha=True)
out.pixels.foreach_set(rec.astype(np.float32).ravel())
out.filepath_raw = os.path.join(AQUI, "logo_lei_seca.png"); out.file_format = "PNG"; out.save()
print("[LOGO] %dx%d -> logo_lei_seca.png (proporcao %.3f, transparencia original: %s)" % (ww, hh, ww / hh, "sim" if px[..., 3].min() < .98 else "nao, fundo branco removido"))
