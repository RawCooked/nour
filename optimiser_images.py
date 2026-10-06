"""Prépare les images du site pour le web.

Usage (depuis le dossier invitation-mariage) :
    pip install pillow numpy
    python optimiser_images.py

1. Dessins du pack « Wedding Invitation Story » (lune, étoile filante, papillons) :
   copiés depuis le Bureau vers img/story/ si besoin, fond crème retiré, -> img/web/
2. Illustrations générées avec ChatGPT, à déposer dans img/art/ :
   - arche.png      : l'illustration brodée principale (arche + coucher de soleil sur la mer)
   - papillons.png  : planche de 6 papillons brodés (3 colonnes x 2 lignes, fond transparent)
   -> converties en WebP ; la planche est découpée en papillon-art-1.webp ... papillon-art-6.webp
"""
import shutil
from pathlib import Path

import numpy as np
from PIL import Image, ImageFilter

ROOT = Path(__file__).parent
SRC = ROOT / "img" / "story"
ART = ROOT / "img" / "art"
OUT = ROOT / "img" / "web"
DESKTOP_PACK = (Path.home() / "Desktop" / "57973095-wedding-invitation-stories-pack-for-after-effects-ShareAE.com"
                / "Wedding Invitation Story Pack" / "(Footage)" / "00_Assets")

# fichier du pack -> (nom de sortie, largeur max, zones à effacer en fractions (x0, y0, x1, y1))
ASSETS = {
    "Crescent Moon With Stars.png": ("lune", 600, [(0.30, 0.95, 0.70, 1.0)]),
    "Stylized Shooting Star Illustration.png": ("etoile-filante", 500, []),
    "Brown Butterfly Silhouette Design.png": ("papillon-brun", 320, [(0.0, 0.0, 0.10, 0.32)]),
    "Green Butterfly Silhouette Design.png": ("papillon-vert", 320, [(0.0, 0.86, 0.04, 1.0)]),
}

for d in (SRC, ART, OUT):
    d.mkdir(parents=True, exist_ok=True)


def trim(im):
    bbox = im.getchannel("A").point(lambda a: 255 if a > 10 else 0).getbbox()
    return im.crop(bbox) if bbox else im


def fit(im, max_w):
    if im.width > max_w:
        im = im.resize((max_w, round(im.height * max_w / im.width)), Image.LANCZOS)
    return im


def save(im, name, quality=85):
    dst = OUT / f"{name}.webp"
    im.save(dst, "WEBP", quality=quality, method=6)
    print(f"  -> {dst.name:<24} {im.width}x{im.height}  {dst.stat().st_size/1024:.0f} Ko")


print("Dessins du pack :")
for name, (out_name, max_w, erase) in ASSETS.items():
    src = SRC / name
    if not src.exists() and (DESKTOP_PACK / name).exists():
        shutil.copy2(DESKTOP_PACK / name, src)
    if not src.exists():
        print(f"  manquant : {src}")
        continue
    rgb = np.asarray(Image.open(src).convert("RGB")).astype(np.float32)
    h, w, _ = rgb.shape
    bright = rgb[rgb.max(axis=2) > 200]
    paper = np.median(bright, axis=0) if len(bright) else np.array([245, 240, 230], np.float32)
    dark = np.clip((paper - rgb) / np.maximum(paper, 1), 0, 1).max(axis=2)
    alpha = np.clip((dark - 0.08) / 0.30, 0, 1)
    for x0, y0, x1, y1 in erase:
        alpha[int(y0 * h):int(y1 * h), int(x0 * w):int(x1 * w)] = 0
    im = Image.fromarray(np.dstack([rgb, alpha * 255]).astype(np.uint8), "RGBA")
    save(fit(trim(im), max_w), out_name)

print("\nFeuillages du modèle Bells (utilisés en silhouettes dorées) :")
BELLS = ROOT / "img" / "bells"
for name, out_name, max_w in [("Leaf-03.png", "leaf-03", 600), ("Leaf-06.png", "leaf-06", 320),
                              ("Leaf-09.png", "leaf-09", 420), ("Leaf-10.png", "leaf-10", 420)]:
    src = BELLS / name
    if src.exists():
        save(fit(trim(Image.open(src).convert("RGBA")), max_w), out_name)
    else:
        print(f"  manquant : {src}")

print("\nCouple de mariés (aquarelle, fond transparent) :")
couple = BELLS / "couple-maries.webp"
if couple.exists():
    save(fit(trim(Image.open(couple).convert("RGBA")), 760), "couple", quality=88)
else:
    print("  manquant : img/bells/couple-maries.webp — la scène « Main dans la main » n'affichera pas le couple")

print("\nCouple qui danse (planche de 30 images, 6 colonnes x 5 lignes, 11 gardées) :")


def runs(profile):
    out, start = [], None
    for i, v in enumerate(profile):
        if v and start is None:
            start = i
        elif not v and start is not None:
            out.append((start, i)); start = None
    if start is not None:
        out.append((start, len(profile)))
    return out


def agrandir(im, k):
    a = np.asarray(im.convert("RGBA")).astype(np.float32) / 255
    a[..., :3] *= a[..., 3:4]
    big = Image.fromarray((a * 255).round().astype(np.uint8), "RGBA").resize((im.width * k, im.height * k), Image.LANCZOS)
    rgb = Image.fromarray(np.asarray(big)[..., :3].copy(), "RGB").filter(ImageFilter.UnsharpMask(1.4, 70, 2))
    out = np.asarray(big).astype(np.float32) / 255
    out[..., :3] = np.minimum(np.asarray(rgb).astype(np.float32) / 255, out[..., 3:4])
    out[..., :3] /= np.maximum(out[..., 3:4], 1e-4)
    return Image.fromarray((np.clip(out, 0, 1) * 255).round().astype(np.uint8), "RGBA")


# Les 30 images de la planche ne forment pas une animation continue (coiffure, visage et robe changent un peu
# d'une image à l'autre) : jouées dans l'ordre, ça saute. On ne garde que les images « calmes » (balancement
# lent), rangées dans l'ordre où elles se ressemblent le plus, et on les fond doucement dans le navigateur.
DANSE_ORDRE = [0, 2, 1, 3, 5, 6, 28, 29, 24, 23, 4]
DANSE_COLS, DANSE_ROWS = 4, 3


def recaler(cells, ref, rayon=5):
    """Décale chaque image de quelques pixels pour que le costume du marié (qui reste en place) coïncide avec la référence."""
    def costume(im):
        a = np.asarray(im).astype(np.float32)
        return (a[..., 3] > 128) & (a[..., :3].mean(axis=2) < 95)
    cible = costume(cells[ref])
    out = []
    for im in cells:
        m = costume(im)
        best, bs = (0, 0), None
        for dy in range(-rayon, rayon + 1):
            for dx in range(-rayon, rayon + 1):
                sc = np.count_nonzero(np.roll(np.roll(m, dy, axis=0), dx, axis=1) ^ cible)
                if bs is None or sc < bs:
                    bs, best = sc, (dx, dy)
        moved = Image.new("RGBA", im.size, (0, 0, 0, 0))
        moved.paste(im, best)
        out.append(moved)
    return out


def couple_danse(src, cols=6, rows=5):
    """Découpe la planche (les couples sont séparés par du vide), cale chaque image sur les chaussures du marié
    (il reste en place, c'est la mariée qui tourne), garde les images calmes et les range en boucle douce."""
    sheet = Image.open(src).convert("RGBA")
    alpha = np.asarray(sheet.getchannel("A")) > 10
    bands = runs(alpha.any(axis=1))
    if len(bands) != rows:
        print(f"  planche inattendue : {len(bands)} lignes au lieu de {rows}")
        return
    frames = []
    for y0, y1 in bands:
        cells = runs(alpha[y0:y1].any(axis=0))
        if len(cells) != cols:
            print(f"  planche inattendue : {len(cells)} colonnes au lieu de {cols}")
            return
        for x0, x1 in cells:
            im = sheet.crop((x0, y0, x1, y1))
            a = np.asarray(im).astype(np.float32)
            dark = (a[..., 3] > 128) & (a[..., :3].mean(axis=2) < 95)      # costume et chaussures du marié
            top = int(im.height * 0.65)
            ys, xs = np.nonzero(dark[top:])
            ys = ys + top
            foot = ys.max()
            ax = xs[ys > foot - 0.08 * im.height].mean()                    # pieds du marié
            frames.append((im, ax, foot))
    frames = [frames[i] for i in DANSE_ORDRE]
    left = max(f[1] for f in frames)
    right = max(f[0].width - f[1] for f in frames)
    up = max(f[2] for f in frames)
    down = max(f[0].height - f[2] for f in frames)
    pad = 10
    cw, ch = int(np.ceil(left + right)) + 2 * pad, int(np.ceil(up + down)) + 2 * pad
    cells = []
    for im, ax, foot in frames:
        c = Image.new("RGBA", (cw, ch), (0, 0, 0, 0))
        c.paste(im, (pad + round(left - ax), pad + round(up - foot)))
        cells.append(c)
    cells = recaler(cells, ref=0)
    atlas = Image.new("RGBA", (cw * DANSE_COLS, ch * DANSE_ROWS), (0, 0, 0, 0))
    for i, c in enumerate(cells):
        atlas.paste(c, ((i % DANSE_COLS) * cw, (i // DANSE_COLS) * ch))
    # La planche source est petite (~180 px par image) : on agrandit avec un filtre doux + un peu de netteté,
    # c'est plus propre que l'agrandissement brut du navigateur. Tout se fait en alpha pré-multiplié
    # (sinon le noir caché sous le transparent bave en liseré sombre sur les bords).
    atlas = agrandir(atlas, 2)
    cw, ch = cw * 2, ch * 2
    save(atlas, "couple-danse", quality=82)
    print(f"  {len(frames)} images de {cw}x{ch} px ; chaussures du marié à {(down * 2 + pad * 2) / ch:.4f} du bas de la case (DANCE_SHOE dans index.html)")


dance = ART / "couple-danse-sprite.webp"
if dance.exists():
    couple_danse(dance)
else:
    print("  manquant : img/art/couple-danse-sprite.webp — la scène utilisera le couple immobile")

print("\nAnimaux qui traversent la plage (planches de 9 images, 3 colonnes x 3 lignes) :")


def detourer(im, ombre=False):
    """Planche à fond uni (aperçu JPEG/PNG sans transparence) : le fond devient transparent.
    Si la planche a déjà de la transparence, on n'y touche pas."""
    im = im.convert("RGBA")
    a = np.asarray(im).astype(np.float32)
    if a[..., 3].min() < 250:
        return im
    h, w, _ = a.shape
    bord = np.concatenate([a[0, :, :3], a[-1, :, :3], a[:, 0, :3], a[:, -1, :3]])
    fond = np.median(bord, axis=0)
    dist = np.abs(a[..., :3] - fond).max(axis=2)
    alpha = np.clip((dist - 30) / 34, 0, 1)
    rgb = a[..., :3]
    if ombre:
        # ombre portée sous l'animal : tons moyens, loin de toute zone sombre -> on la retire (la scène a la sienne)
        lum = rgb.mean(axis=2)
        sombre = Image.fromarray(((lum < 110) * 255).astype(np.uint8)).filter(ImageFilter.MaxFilter(9))
        pres = np.asarray(sombre) > 0
        alpha[(lum > 140) & (lum < 212) & ~pres] = 0
    # défrange : on retire la part de couleur de fond qui reste dans les bords translucides
    col = (rgb - (1 - alpha[..., None]) * fond) / np.maximum(alpha[..., None], 0.05)
    col = np.clip(np.where(alpha[..., None] > 0.05, col, rgb), 0, 255)
    return Image.fromarray(np.dstack([col, alpha * 255]).astype(np.uint8), "RGBA")


def animal(src, name, cols=3, rows=3, agrandi=1, ombre=False):
    """Découpe une planche de marche/course (les images sont séparées par du vide), cale chaque image
    (pattes au sol, corps centré) et range le tout en atlas."""
    sheet = detourer(Image.open(src), ombre)
    alpha = np.asarray(sheet.getchannel("A")) > 40
    bands = runs(alpha.any(axis=1))
    # miettes (filigrane, bords) : on ignore les bandes minuscules
    bands = [b for b in bands if b[1] - b[0] > 0.04 * sheet.height]
    if len(bands) != rows:
        print(f"  {name} : {len(bands)} lignes au lieu de {rows}")
        return
    frames = []
    for y0, y1 in bands:
        cells = [c for c in runs(alpha[y0:y1].any(axis=0)) if c[1] - c[0] > 0.04 * sheet.width]
        if len(cells) != cols:
            print(f"  {name} : {len(cells)} colonnes au lieu de {cols}")
            return
        for x0, x1 in cells:
            im = sheet.crop((x0, y0, x1, y1))
            al = np.asarray(im.getchannel("A")) > 128
            ys = np.nonzero(al.any(axis=1))[0]
            im = im.crop((0, ys.min(), im.width, ys.max() + 1))
            al = al[ys.min(): ys.max() + 1]
            xs = np.nonzero(al[: max(1, int(al.shape[0] * 0.55))])[1]     # tête, dos, queue
            frames.append((im, xs.mean(), im.height - 1))
    left = max(f[1] for f in frames)
    right = max(f[0].width - f[1] for f in frames)
    up = max(f[2] for f in frames)
    pad = 4
    cw, ch = int(np.ceil(left + right)) + 2 * pad, int(np.ceil(up)) + 1 + 2 * pad
    atlas = Image.new("RGBA", (cw * cols, ch * rows), (0, 0, 0, 0))
    for i, (im, ax, foot) in enumerate(frames):
        atlas.paste(im, ((i % cols) * cw + pad + round(left - ax), (i // cols) * ch + pad + round(up - foot)))
    if agrandi > 1:
        atlas = agrandir(atlas, agrandi)
        cw, ch = cw * agrandi, ch * agrandi
    save(atlas, name, quality=88)
    print(f"  {len(frames)} images de {cw}x{ch} px ; pattes à {pad * agrandi / ch:.4f} du bas de la case (paw de {name} dans index.html)")


for fichier, nom, opts in (("chien-or-sprite", "chien-or", {}), ("chat-sprite", "chat", {"ombre": True, "agrandi": 2}),
                           ("chien-marche-sprite", "chien-marche", {"cols": 4, "rows": 3})):
    src = next((q for q in (ART / f"{fichier}.png", ART / f"{fichier}.webp") if q.exists()), None)
    if src:
        animal(src, nom, **opts)
    else:
        print(f"  manquant : img/art/{fichier}.png")

print("\nIllustrations ChatGPT (img/art/) :")
arche = next((p for p in (ART / "arche.png", ART / "arche.jpg", ART / "arche.webp") if p.exists()), None)
if arche:
    save(fit(Image.open(arche).convert("RGB"), 1100), "arche", quality=82)
else:
    print("  pas encore d'arche.png — le site affiche l'arche dessinée en CSS")

planche = next((p for p in (ART / "papillons.png", ART / "papillons.webp") if p.exists()), None)
if planche:
    sheet = Image.open(planche).convert("RGBA")
    # fond blanc au lieu de transparent : on le retire
    arr = np.asarray(sheet).astype(np.float32)
    if arr[..., 3].min() > 250:
        white = arr[..., :3].min(axis=2)
        arr[..., 3] = np.clip((255 - white) / 40, 0, 1) * 255
        sheet = Image.fromarray(arr.astype(np.uint8), "RGBA")
    cw, ch = sheet.width / 3, sheet.height / 2
    n = 0
    for row in range(2):
        for col in range(3):
            cell = sheet.crop((round(col * cw), round(row * ch), round((col + 1) * cw), round((row + 1) * ch)))
            cell = trim(cell)
            if cell.getbbox():
                n += 1
                save(fit(cell, 260), f"papillon-art-{n}")
else:
    print("  pas encore de papillons.png — le site utilise les papillons du pack")
