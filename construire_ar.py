"""Fabrique la version arabe du site (publiée sur /ar/) à partir de index.html.

C'est la même page : seul le réglage de langue par défaut change, plus les balises de partage
(titre, description) pour que l'aperçu WhatsApp soit en arabe.

Usage :  python construire_ar.py [dossier de sortie]      (par défaut : ./ar)
La mise en ligne l'exécute automatiquement.
"""
import re
import sys
from pathlib import Path

ROOT = Path(__file__).parent
sortie = Path(sys.argv[1]) if len(sys.argv) > 1 else ROOT / "ar"
html = (ROOT / "index.html").read_text(encoding="utf-8")


def remplacer(motif, texte, n=1):
    global html
    html, k = re.subn(motif, lambda _: texte, html, count=n)
    if k != n:
        sys.exit(f"construire_ar : motif introuvable : {motif}")


remplacer(r'<html lang="fr">', '<html lang="ar" dir="rtl">')
remplacer(r'window\.LANG_DEFAULT = "fr";', 'window.LANG_DEFAULT = "ar";')
# la page vit dans /ar/ : les images restent cherchées à la racine du site
# (pas de <base>, qui casserait les liens d'ancre comme #lieu)
html = html.replace("img/web/", "/img/web/")
remplacer(r"<title>.*?</title>", "<title>نور وعصام</title>")
remplacer(r'<meta name="description" content="[^"]*">',
          '<meta name="description" content="دعوة لحضور حفل زفاف نور وعصام — الأحد 18 أكتوبر 2026، من 18:00 إلى 21:00">')
remplacer(r'<meta property="og:title" content="[^"]*">', '<meta property="og:title" content="نور وعصام — دعوة زفاف">')
remplacer(r'<meta property="og:description" content="[^"]*">',
          '<meta property="og:description" content="الأحد 18 أكتوبر 2026، من 18:00 إلى 21:00، في فضاء نهاوند. المسوا الختم لفتح الدعوة.">')

sortie.mkdir(parents=True, exist_ok=True)
(sortie / "index.html").write_text(html, encoding="utf-8")
print(f"  -> {sortie / 'index.html'}")
