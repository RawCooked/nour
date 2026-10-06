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
from PIL import Image

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
