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

print("\nCouple qui danse (planche de 30 images, 6 colonnes x 5 lignes) :")


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


def couple_danse(src, cols=6, rows=5):
    """Découpe la planche (les couples sont séparés par du vide), puis cale chaque image sur les chaussures
    du marié (il reste en place, c'est la mariée qui tourne) : les 30 images tiennent dans des cases identiques."""
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
    left = max(f[1] for f in frames)
    right = max(f[0].width - f[1] for f in frames)
    up = max(f[2] for f in frames)
    down = max(f[0].height - f[2] for f in frames)
    pad = 6
    cw, ch = int(np.ceil(left + right)) + 2 * pad, int(np.ceil(up + down)) + 2 * pad
    atlas = Image.new("RGBA", (cw * cols, ch * rows), (0, 0, 0, 0))
    for i, (im, ax, foot) in enumerate(frames):
        ox = (i % cols) * cw + pad + round(left - ax)
        oy = (i // cols) * ch + pad + round(up - foot)
        atlas.paste(im, (ox, oy))
    # La planche source est petite (~180 px par image) : on agrandit avec un filtre doux + un peu de netteté,
    # c'est plus propre que l'agrandissement brut du navigateur. Tout se fait en alpha pré-multiplié
    # (sinon le noir caché sous le transparent bave en liseré sombre sur les bords).
    atlas = agrandir(atlas, 2)
    cw, ch = cw * 2, ch * 2
    save(atlas, "couple-danse", quality=78)
    print(f"  {len(frames)} images de {cw}x{ch} px ; chaussures du marié à {(down * 2 + pad * 2) / ch:.4f} du bas de la case (DANCE_SHOE dans index.html)")


dance = ART / "couple-danse-sprite.webp"
if dance.exists():
    couple_danse(dance)
else:
    print("  manquant : img/art/couple-danse-sprite.webp — la scène utilisera le couple immobile")

print("\nChien qui marche (planche de 12 images, 4 colonnes x 3 lignes) :")


def chien_marche(src, cols=4, rows=3):
    """Même principe que le couple : découpe, puis cale chaque image (pattes au sol, corps centré)."""
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
            al = np.asarray(im.getchannel("A")) > 128
            xs = np.nonzero(al[: int(im.height * 0.55)])[1]       # tête, dos, queue : ne bougent presque pas
            frames.append((im, xs.mean(), im.height - 1))
    left = max(f[1] for f in frames)
    right = max(f[0].width - f[1] for f in frames)
    up = max(f[2] for f in frames)
    pad = 4
    cw, ch = int(np.ceil(left + right)) + 2 * pad, int(np.ceil(up)) + 1 + 2 * pad
    atlas = Image.new("RGBA", (cw * cols, ch * rows), (0, 0, 0, 0))
    for i, (im, ax, foot) in enumerate(frames):
        atlas.paste(im, ((i % cols) * cw + pad + round(left - ax), (i // cols) * ch + pad + round(up - foot)))
    save(atlas, "chien-marche", quality=88)
    print(f"  {len(frames)} images de {cw}x{ch} px ; pattes à {pad / ch:.4f} du bas de la case (DOG_PAW dans index.html)")


walk = ART / "chien-marche-sprite.webp"
if walk.exists():
    chien_marche(walk)
else:
    print("  manquant : img/art/chien-marche-sprite.webp — la scène n'affichera pas le chien")

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
