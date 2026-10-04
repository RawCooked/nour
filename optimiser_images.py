"""Prépare les dessins du pack « Wedding Invitation Story » pour le web.

Usage (depuis le dossier invitation-mariage) :
    pip install pillow numpy
    python optimiser_images.py

1. Copie les dessins utilisés depuis le Bureau vers img/story/ (une seule fois,
   pour qu'ils soient dans le dépôt Git et que la mise en ligne les retrouve).
2. Retire le fond crème (le trait devient opaque, le papier transparent),
   efface les morceaux d'autres éléments restés dans certains fichiers,
   recadre et enregistre en WebP dans img/web/.
"""
import shutil
from pathlib import Path

import numpy as np
from PIL import Image

ROOT = Path(__file__).parent
SRC = ROOT / "img" / "story"
OUT = ROOT / "img" / "web"
DESKTOP_PACK = (Path.home() / "Desktop" / "57973095-wedding-invitation-stories-pack-for-after-effects-ShareAE.com"
                / "Wedding Invitation Story Pack" / "(Footage)" / "00_Assets")

# fichier du pack -> (nom de sortie, largeur max, zones à effacer en fractions (x0, y0, x1, y1))
ASSETS = {
    "Crescent Moon With Stars.png": ("lune", 600, [(0.30, 0.95, 0.70, 1.0)]),            # bout de lettre en bas
    "Stylized Shooting Star Illustration.png": ("etoile-filante", 500, []),
    "Brown Butterfly Silhouette Design.png": ("papillon-brun", 320, [(0.0, 0.0, 0.10, 0.32)]),  # chiffre « 4 »
    "Green Butterfly Silhouette Design.png": ("papillon-vert", 320, [(0.0, 0.86, 0.04, 1.0)]),  # lettre « S »
    "Simple Mountain Line Drawing.png": ("montagnes", 1400, []),
}

SRC.mkdir(parents=True, exist_ok=True)
OUT.mkdir(parents=True, exist_ok=True)

total_before = total_after = 0
for name, (out_name, max_w, erase) in ASSETS.items():
    src = SRC / name
    if not src.exists() and (DESKTOP_PACK / name).exists():
        shutil.copy2(DESKTOP_PACK / name, src)
        print(f"  copié depuis le Bureau : {name}")
    if not src.exists():
        print(f"  manquant : {src}")
        continue

    rgb = np.asarray(Image.open(src).convert("RGB")).astype(np.float32)
    h, w, _ = rgb.shape

    # couleur du papier = médiane des pixels clairs
    bright = rgb[rgb.max(axis=2) > 200]
    paper = np.median(bright, axis=0) if len(bright) else np.array([245, 240, 230], np.float32)

    # plus le pixel est sombre par rapport au papier, plus il est opaque
    dark = np.clip((paper - rgb) / np.maximum(paper, 1), 0, 1).max(axis=2)
    alpha = np.clip((dark - 0.08) / 0.30, 0, 1)

    for x0, y0, x1, y1 in erase:
        alpha[int(y0 * h):int(y1 * h), int(x0 * w):int(x1 * w)] = 0

    im = Image.fromarray(np.dstack([rgb, alpha * 255]).astype(np.uint8), "RGBA")
    bbox = Image.fromarray((alpha * 255).astype(np.uint8)).point(lambda a: 255 if a > 10 else 0).getbbox()
    if bbox:
        im = im.crop(bbox)
    if im.width > max_w:
        im = im.resize((max_w, round(im.height * max_w / im.width)), Image.LANCZOS)

    dst = OUT / f"{out_name}.webp"
    im.save(dst, "WEBP", quality=85, method=6)
    before, after = src.stat().st_size, dst.stat().st_size
    total_before += before
    total_after += after
    print(f"  {name:<42} {before/1024:6.0f} Ko -> {after/1024:4.0f} Ko  ({dst.name}, {im.width}x{im.height})")

print(f"\nTotal : {total_before/1024/1024:.1f} Mo -> {total_after/1024:.0f} Ko")
