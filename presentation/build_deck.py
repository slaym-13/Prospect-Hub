"""Builds the project presentation with python-pptx.

    pip install python-pptx
    python presentation/build_deck.py                 # -> presentation/deck_generated.pptx
    python presentation/build_deck.py --out other.pptx

Run it from the repository root: every path below is relative to it. The figures come
from analysis/outputs/figures, so run the Python pipeline first.

The final deck, IOADA202_HARMACH_SOULAIMANE_VF.pptx, was finished by hand in Google
Slides after being generated. This script writes to another file by default so it never
overwrites those edits; pass --out explicitly to replace it.
"""
import argparse
import os
import uuid

from lxml import etree
from PIL import Image
from pptx import Presentation
from pptx.dml.color import RGBColor
from pptx.enum.shapes import MSO_SHAPE
from pptx.enum.text import MSO_ANCHOR, PP_ALIGN
from pptx.oxml.ns import qn
from pptx.util import Emu, Inches, Pt


def FIG(n):
    return os.path.join('analysis', 'outputs', 'figures', f'{n}.png')


def BG(n):
    return os.path.join('presentation', 'assets', f'bg_{n}.png')


# ------------------------------------------------------------------ theme
# The palette is the application's own (client/src/theme.css), so the deck and the
# product read as one thing.
THEME = {
    'name': 'Prospect Hub',
    'font': 'Roboto',
    'colors': {
        'dk1': '0B0B0B', 'lt1': 'FFFFFF', 'dk2': '52514E', 'lt2': 'F4F7FB',
        'accent1': '2A78D6', 'accent2': '86B6EF', 'accent3': '104281',
        'accent4': '0CA30C', 'accent5': 'B8860B', 'accent6': 'B02A2A',
        'hlink': '2A78D6', 'folHlink': '104281',
    },
}
INK, MUTED, ACCENT, DEEP = '0B0B0B', '52514E', '2A78D6', '104281'
SOFT, SURFACE, GOOD, WARN, BAD = 'E3EFFC', 'FFFFFF', '0CA30C', 'B8860B', 'B02A2A'

W, H = 13.333, 7.5          # 16:9 wide
M = 0.72                    # page margin
COL = W - M * 2             # usable width
GAP = 0.4                   # gutter between two columns
C2 = (COL - GAP) / 2        # width of one of two columns
RIGHT = M + C2 + GAP        # x of the right column

pres = Presentation()
pres.slide_width, pres.slide_height = Inches(W), Inches(H)
pres.core_properties.author = 'HARMACH Soulaimane'
pres.core_properties.title = 'Prospect Hub — plateforme de prospection et de candidature'
BLANK = pres.slide_layouts[6]
SECTIONS = []               # (name, [slides]) in order


def rgb(h):
    return RGBColor.from_string(h)


# ------------------------------------------------------------- primitives
ALIGN = {'left': PP_ALIGN.LEFT, 'center': PP_ALIGN.CENTER, 'right': PP_ALIGN.RIGHT}
ANCHOR = {'top': MSO_ANCHOR.TOP, 'middle': MSO_ANCHOR.MIDDLE, 'bottom': MSO_ANCHOR.BOTTOM}


def text(slide, value, x, y, w, h, size=12, color=MUTED, bold=False, italic=False, align='left',
         valign='top', spacing=None, bullets=False, after=0):
    """A text box. A newline starts a new paragraph; a list gives one paragraph per item."""
    box = slide.shapes.add_textbox(Inches(x), Inches(y), Inches(w), Inches(h))
    tf = box.text_frame
    tf.word_wrap = True
    tf.margin_left = tf.margin_right = tf.margin_top = tf.margin_bottom = 0
    tf.vertical_anchor = ANCHOR[valign]
    items = value if isinstance(value, list) else str(value).split('\n')
    for i, item in enumerate(items):
        para = tf.paragraphs[0] if i == 0 else tf.add_paragraph()
        para.alignment = ALIGN[align]
        if spacing:
            para.line_spacing = spacing
        if after:
            para.space_after = Pt(after)
        if bullets:
            pPr = para._p.get_or_add_pPr()
            pPr.set('marL', str(Emu(Pt(14))))
            pPr.set('indent', str(-Emu(Pt(14))))
            bu = etree.SubElement(pPr, qn('a:buChar'))
            bu.set('char', '•')
        run = para.add_run()
        run.text = item
        f = run.font
        f.size, f.bold, f.italic, f.name = Pt(size), bold, italic, THEME['font']
        f.color.rgb = rgb(color)
    return box


def shadow(shape):
    """A soft outer shadow, like the app's cards."""
    spPr = shape._element.spPr
    eff = etree.SubElement(spPr, qn('a:effectLst'))
    sh = etree.SubElement(eff, qn('a:outerShdw'), blurRad=str(Emu(Pt(10))), dist=str(Emu(Pt(2))),
                          dir='5400000', algn='t', rotWithShape='0')
    clr = etree.SubElement(sh, qn('a:srgbClr'), val='1E3A5F')
    etree.SubElement(clr, qn('a:alpha'), val='10000')


def rounded(slide, x, y, w, h, fill, line, radius):
    s = slide.shapes.add_shape(MSO_SHAPE.ROUNDED_RECTANGLE, Inches(x), Inches(y), Inches(w), Inches(h))
    s.adjustments[0] = min(0.5, radius / min(w, h))
    s.fill.solid()
    s.fill.fore_color.rgb = rgb(fill)
    s.line.color.rgb = rgb(line)
    s.line.width = Pt(1)
    return s


def card(slide, x, y, w, h, fill=SURFACE, line='E8EDF5', name='card'):
    """The motif: a soft rounded card, exactly like the surfaces in the app."""
    s = rounded(slide, x, y, w, h, fill, line, 0.14)
    s.name = name
    shadow(s)
    return s


TONES = {'info': (SOFT, ACCENT), 'good': ('DFF3DF', GOOD), 'warn': ('FBF0D8', WARN),
         'bad': ('F7E2E2', BAD), 'grey': ('EFEFEA', MUTED)}


def chip(slide, x, y, label, tone='info', w=1.25):
    """A pill chip, the app's label."""
    bg, fg = TONES[tone]
    rounded(slide, x, y, w, 0.3, bg, bg, 0.15).name = f'chip-{label}'
    text(slide, label, x, y, w, 0.3, size=11.5, bold=True, color=fg, align='center', valign='middle')


def stat(slide, x, y, w, value, label, tone=ACCENT, h=1.28):
    """A headline figure with its caption, on its own card."""
    card(slide, x, y, w, h, name=f'stat-{label}')
    text(slide, value, x + 0.22, y + 0.14, w - 0.44, 0.62, size=34, bold=True, color=tone, valign='middle')
    text(slide, label, x + 0.22, y + 0.74, w - 0.44, 0.42, size=12)


def dot(slide, x, y, n):
    s = slide.shapes.add_shape(MSO_SHAPE.OVAL, Inches(x), Inches(y), Inches(0.4), Inches(0.4))
    s.fill.solid()
    s.fill.fore_color.rgb = rgb(ACCENT)
    s.line.color.rgb = rgb(ACCENT)
    text(slide, str(n), x, y, 0.4, 0.4, size=13, bold=True, color='FFFFFF', align='center', valign='middle')


def step(slide, x, y, w, n, title, body, h=1.75):
    """Numbered step, used for the pipeline and the architecture."""
    card(slide, x, y, w, h, name=f'step-{n}')
    dot(slide, x + 0.22, y + 0.22, n)
    text(slide, title, x + 0.72, y + 0.22, w - 0.94, 0.42, size=14, bold=True, color=INK, valign='middle')
    text(slide, body, x + 0.22, y + 0.72, w - 0.44, h - 0.92, size=12.5, spacing=1.15)


def bullets(slide, x, y, w, h, items, size=13.5):
    """Bulleted list inside a card."""
    text(slide, items, x, y, w, h, size=size, spacing=1.12, bullets=True, after=7)


def image(slide, path, x, y, w, h):
    """A picture scaled to fit the box, centred, keeping its proportions."""
    with Image.open(path) as im:
        iw, ih = im.size
    scale = min(w / iw, h / ih)
    pw, ph = iw * scale, ih * scale
    slide.shapes.add_picture(path, Inches(x + (w - pw) / 2), Inches(y + (h - ph) / 2), Inches(pw), Inches(ph))


def slide_number(slide):
    box = text(slide, '', 12.1, 6.78, 0.5, 0.3, size=11, align='right')
    para = box.text_frame.paragraphs[0]
    r = para.runs[0]._r
    fld = etree.Element(qn('a:fld'), id='{' + str(uuid.uuid4()).upper() + '}', type='slidenum')
    fld.append(r.find(qn('a:rPr')))
    t = etree.SubElement(fld, qn('a:t'))
    t.text = str(len(pres.slides))
    r.addprevious(fld)
    para._p.remove(r)


def new_slide(section, bg):
    s = pres.slides.add_slide(BLANK)
    s.shapes.add_picture(BG(bg), 0, 0, pres.slide_width, pres.slide_height)
    if not SECTIONS or SECTIONS[-1][0] != section:
        SECTIONS.append((section, []))
    SECTIONS[-1][1].append(s)
    return s


def notes(slide, value):
    slide.notes_slide.notes_text_frame.text = value


# ---------------------------------------------------------------- layouts
def title_slide(section, title, body):
    s = new_slide(section, 'title')
    text(s, title, M, 2.25, 9.4, 1.5, size=54, bold=True, color=INK, valign='bottom')
    text(s, body, M, 3.85, 8.6, 1.1, size=19)
    return s


def section_slide(section, title, body):
    s = new_slide(section, 'closing')
    text(s, title, M, 2.9, 10.5, 1.1, size=40, bold=True, color=INK, valign='middle')
    text(s, body, M, 4.05, 9.4, 0.8, size=17)
    return s


def content(section, title, subtitle=None):
    s = new_slide(section, 'content')
    text(s, title, M, 0.46, COL, 0.72, size=32, bold=True, color=INK, valign='middle')
    if subtitle:
        text(s, subtitle, M, 1.2, COL, 0.42, size=15)
    slide_number(s)
    return s


def closing_slide(section, title):
    s = new_slide(section, 'closing')
    text(s, title, M, 2.6, 10.5, 1.2, size=44, bold=True, color=INK, valign='middle')
    return s


# ===================================================================== 1
s = title_slide('Ouverture', 'Prospect Hub',
                'Rechercher, analyser et contacter les entreprises de Marrakech\n'
                'pour décrocher un stage ou une opportunité professionnelle')
chip(s, M, 1.78, 'PROJET DATA · VERSION FINALE', 'info', 3.3)
text(s, '283 entreprises collectées  ·  Python · Flask · React · Gemini', M, 5.25, 9, 0.4, size=14)
text(s, 'HARMACH Soulaimane', M, 5.74, 9, 0.38, size=16, bold=True, color=INK)
text(s, 'Groupe IOADA202', M, 6.1, 9, 0.34, size=13.5)
notes(s, "Bonjour. Je vous présente Prospect Hub, une plateforme qui part d'une liste brute de 283 entreprises de Marrakech collectées sur Google Places, et qui va jusqu'à l'envoi d'une candidature spontanée et au suivi de la réponse. Je vais dérouler la chaîne complète : collecte, exploration, nettoyage en Python, analyse, puis la plateforme elle-même.")

# ===================================================================== 2
s = content('Ouverture', 'Au programme', 'Quatre temps, de la donnée brute à la plateforme en ligne')
w = (COL - 0.36 * 3) / 4
for i, (n, t, b) in enumerate([
    ('1', 'Le problème', 'Pourquoi chercher un stage à Marrakech est inefficace, et ce que la plateforme vise'),
    ('2', 'La donnée', 'Collecte Google Places, exploration, nettoyage Python, analyse'),
    ('3', 'La solution', 'Architecture, backend, frontend, intelligence artificielle'),
    ('4', 'Les résultats', "Ce qui fonctionne aujourd'hui et ce qui reste à faire"),
]):
    step(s, M + i * (w + 0.36), 2.05, w, n, t, b, 2.5)
text(s, "Chaque chiffre présenté vient du fichier réellement collecté et traité — aucune donnée d'exemple.",
     M, 5.0, COL, 0.4, size=13.5, italic=True, color=ACCENT)
notes(s, "Je commence par le problème, puis la démarche data qui est le cœur du projet, ensuite la solution technique, et je termine par les résultats mesurés et les limites.")

# ===================================================================== 3
s = content('Problématique', 'Problématique et objectifs',
            'Chercher un stage à Marrakech se fait encore à la main, entreprise par entreprise')
card(s, M, 1.9, 6.1, 3.5, name='probleme')
chip(s, M + 0.28, 2.12, 'LE PROBLÈME', 'bad', 1.6)
text(s, 'Aucune liste exploitable', M + 0.28, 2.55, 5.5, 0.4, size=19, bold=True, color=INK)
bullets(s, M + 0.28, 3.02, 5.5, 2.2, [
    "Les offres de stage publiées ne couvrent qu'une fraction du marché local",
    'Les entreprises sont dispersées sur Google Maps, sans contact direct',
    'Une candidature spontanée se prépare à la main : trouver, rédiger, envoyer, noter',
    'Rien ne dit par où commencer ni qui relancer',
])
card(s, M + 6.4, 1.9, COL - 6.4, 3.5, fill=SOFT, line='CFE2F7', name='objectifs')
chip(s, M + 6.68, 2.12, 'LES OBJECTIFS', 'info', 1.7)
text(s, 'Une chaîne complète, automatisée', M + 6.68, 2.55, 5.0, 0.4, size=19, bold=True, color=INK)
bullets(s, M + 6.68, 3.02, 5.0, 2.2, [
    "Collecter et fiabiliser une base d'entreprises réelles",
    'Classer les entreprises par potentiel plutôt que par ordre alphabétique',
    "Rédiger la candidature avec l'IA et l'envoyer depuis la plateforme",
    "Suivre chaque échange jusqu'à la réponse",
])
notes(s, "Le point de départ est concret : à Marrakech, les offres de stage publiées ne représentent qu'une petite partie du marché. L'essentiel passe par la candidature spontanée. Le problème n'est donc pas de lire des annonces, mais de construire soi-même une liste d'entreprises, de la prioriser, et de ne rien perdre en route. C'est exactement ce que la plateforme industrialise.")

# ===================================================================== 4
s = content('Architecture', 'Architecture globale', 'Quatre couches, une seule source de vérité pour les données')
w = (COL - 0.34 * 3) / 4
for i, (t, b, tone) in enumerate([
    ('Collecte', 'Google Places API\n14 requêtes ciblées\n→ companies.csv', 'grey'),
    ('Traitement', 'Python · pandas\nexplorer → nettoyer → analyser\n→ companies_clean.csv', 'warn'),
    ('Service', 'Python · Flask 3\n36 endpoints REST\ndb.json + logique métier', 'info'),
    ('Interface', 'React 19 · Vite · Tailwind\n6 pages, Chart.js\n+ assistant Gemini', 'good'),
]):
    x = M + i * (w + 0.34)
    card(s, x, 2.0, w, 2.35, name=f'layer-{t}')
    chip(s, x + 0.24, 2.22, t.upper(), tone, w - 0.48)
    text(s, b, x + 0.24, 2.68, w - 0.48, 1.5, size=12.5, spacing=1.2)
    if i < 3:
        text(s, '→', x + w + 0.02, 2.9, 0.3, 0.4, size=18, bold=True, color=ACCENT, align='center', valign='middle')
card(s, M, 4.62, COL, 1.35, fill=SOFT, line='CFE2F7', name='flux')
text(s, 'Le même fichier CSV alimente les deux branches', M + 0.3, 4.78, 6, 0.35, size=15, bold=True, color=INK)
text(s, "L'analyse Python et l'application lisent la même source. Le score d'opportunité est implémenté deux fois avec la même formule — une fois en Python pour le rapport, une fois dans le navigateur pour l'application — ce qui garantit que les chiffres des slides et ceux de l'écran ne divergent jamais.",
     M + 0.3, 5.15, COL - 0.6, 0.7, size=12.5, spacing=1.15)
notes(s, "L'architecture se lit de gauche à droite. La collecte produit un CSV. Python le nettoie et l'analyse. Flask, en Python, le sert et porte la logique métier. React l'affiche. Point important pour la cohérence : le score d'opportunité existe à deux endroits, l'analyse Python et le navigateur, avec la même formule et les mêmes poids, donc ce que je montre dans les graphiques est exactement ce que l'utilisateur voit dans l'application.")

# ===================================================================== 5
s = content('Architecture', 'Stack technique et outils', 'Choisis pour la rapidité de développement et la simplicité de déploiement')
w = (COL - 0.34 * 3) / 4
for i, (title, items) in enumerate([
    ('Données', ['Python 3.14', 'pandas — nettoyage et agrégation', 'matplotlib — 10 figures', 'NumPy — statistiques']),
    ('Backend', ['Python 3.10+ · Flask 3', 'db.json — base fichier JSON', 'bcrypt · cookies signés HMAC', 'smtplib — envoi SMTP']),
    ('Frontend', ['React 19 — 37 modules', 'Vite 7 — build en 1,8 s', 'Tailwind CSS 4 — thème unique', 'Chart.js 4 — graphiques']),
    ('IA & API', ['Google Gemini 2.5 Flash', 'Google Places API', 'clé par utilisateur, chiffrée', 'assistant intégré']),
]):
    x = M + i * (w + 0.34)
    card(s, x, 2.0, w, 3.1, name=f'stack-{title}')
    text(s, title, x + 0.26, 2.2, w - 0.52, 0.38, size=17, bold=True, color=ACCENT)
    bullets(s, x + 0.26, 2.68, w - 0.52, 2.2, items, 12.5)
text(s, 'Python de bout en bout côté serveur — données, API, logique métier — et JavaScript seulement dans le navigateur.',
     M, 5.35, COL, 0.5, size=13.5, italic=True)
notes(s, "Je justifie deux choix. D'abord Python pour la partie data : pandas est l'outil standard pour ce volume et ces opérations. Ensuite Python aussi pour le serveur, avec Flask : le même langage sert la chaîne de données, l'API et la logique métier, et JavaScript ne reste que là où il est incontournable, dans le navigateur. La base est un simple fichier JSON : pour 283 entreprises et un utilisateur, une base relationnelle serait une complexité inutile — mais je sais que c'est la première chose à changer pour passer à l'échelle.")

# ===================================================================== 6
s = content('Architecture', 'Backend : API, logique métier et données', 'Python · Flask 3 — 36 endpoints REST, 10 modules')
card(s, M, 1.95, 7.3, 3.6, name='modules')
text(s, 'Organisation en modules', M + 0.3, 2.12, 4, 0.38, size=17, bold=True, color=INK)
for i, (name, desc) in enumerate([
    ('store.py', 'lecture/écriture du CSV et de db.json, export'),
    ('api.py', 'les 26 routes REST et la validation des entrées'),
    ('auth.py', 'comptes, sessions signées, chiffrement de la clé IA'),
    ('ai.py', 'appels Gemini : rédaction des emails'),
    ('assistant.py', "base de connaissances + mémoire de l'assistant"),
    ('mailer.py', 'envoi SMTP, en-tête de désinscription'),
    ('jobs.py', "tâches de fond avec suivi d'avancement"),
]):
    y = 2.62 + i * 0.4
    text(s, name, M + 0.3, y, 1.5, 0.34, size=12.5, bold=True, color=ACCENT, valign='middle')
    text(s, desc, M + 1.85, y, 5.2, 0.34, size=12.5, valign='middle')
card(s, M + 7.6, 1.95, COL - 7.6, 3.6, fill=SOFT, line='CFE2F7', name='regles')
text(s, 'La logique métier, côté serveur', M + 7.88, 2.12, 4.0, 0.42, size=16, bold=True, color=INK)
bullets(s, M + 7.88, 2.62, 3.9, 2.8, [
    'Plafond quotidien d’envois (20 par défaut)',
    'Interdiction de réécrire au même contact sous 14 jours',
    'Statut « ne pas contacter » bloquant',
    'Ligne de désinscription ajoutée à chaque message',
    'Idempotence : un double clic n’envoie qu’un email',
    'Le passage d’un contact enregistré fait avancer le statut',
], 12.5)
text(s, 'Ces règles vivent dans l’API, pas dans l’interface : elles s’appliquent même si quelqu’un appelle l’API directement.',
     M, 5.72, COL, 0.45, size=13, italic=True, color=ACCENT)
notes(s, "Le backend est écrit en Python avec Flask, et découpé par responsabilité, un module par sujet. Le point que je veux souligner, c'est que toutes les règles métier sont côté serveur : le plafond d'envoi, le délai de 14 jours entre deux messages, le statut « ne pas contacter ». Si on contournait l'interface et qu'on appelait l'API directement, ces règles s'appliqueraient quand même. C'est volontaire : la conformité ne doit pas dépendre du bouton.")

# ===================================================================== 7
s = section_slide('Données', 'La démarche data', 'Collecte → exploration → nettoyage → analyse')
chip(s, M, 2.42, 'PARTIE 2', 'info', 1.5)
notes(s, "J'en viens au cœur du projet : la chaîne de traitement des données.")

# ===================================================================== 8
s = content('Données', 'Sources de données et méthodologie de collecte',
            'Google Places API (New) — les données publiques des fiches entreprise')
w = (COL - 0.34 * 2) / 3
step(s, M, 1.95, w, '1', '14 requêtes ciblées',
     'Des recherches croisant métier et ville : « agence digitale Marrakech », « société informatique Marrakech », « hôtel Marrakech »… pour couvrir plusieurs secteurs plutôt qu’un seul.', 2.45)
step(s, M + w + 0.34, 1.95, w, '2', 'Déduplication à la source',
     'Le place_id de Google sert de clé unique : une entreprise trouvée par trois requêtes différentes n’est enregistrée qu’une fois.', 2.45)
step(s, M + (w + 0.34) * 2, 1.95, w, '3', '13 champs par entreprise',
     'Nom, adresse, téléphone, site web, catégorie, note, nombre d’avis, latitude, longitude, lien Maps, et la requête d’origine.', 2.45)
stat(s, M, 4.68, 2.4, '283', 'entreprises collectées')
stat(s, M + 2.6, 4.68, 2.4, '14', 'requêtes de recherche')
stat(s, M + 5.2, 4.68, 2.4, '13', 'champs par entreprise')
card(s, M + 7.8, 4.68, COL - 7.8, 1.28, fill=SOFT, line='CFE2F7', name='limite-collecte')
text(s, 'Limite assumée', M + 8.05, 4.82, 3.6, 0.32, size=13.5, bold=True, color=INK)
text(s, "Google Places ne fournit jamais d'adresse email. C'est la contrainte qui structure toute la suite.",
     M + 8.05, 5.16, 3.8, 0.7, size=12, spacing=1.12)
notes(s, "La source est l'API Google Places. J'ai utilisé 14 requêtes croisant un métier et la ville pour ne pas me limiter à un seul secteur. Le place_id sert de clé de déduplication dès la collecte. Point important pour la suite : Google ne donne jamais l'email. C'est pour ça que la moitié du fichier arrive sans adresse, et c'est la contrainte principale du projet.")

# ===================================================================== 9
s = content('Données', 'Exploration : comprendre avant de corriger',
            'Le script 01_explore.py mesure l’état du fichier brut sans rien modifier')
image(s, FIG('01_missing'), M, 1.82, 6.2, 2.75)
image(s, FIG('02_categories_raw'), M, 4.6, 6.2, 2.4)
card(s, M + 6.6, 1.82, COL - 6.6, 5.18, name='constats')
text(s, 'Ce que l’exploration révèle', M + 6.9, 2.0, 5.2, 0.4, size=18, bold=True, color=INK)
for i, (n, t, c) in enumerate([
    ('50 %', 'des entreprises n’ont pas d’email — la contrainte Google Places', BAD),
    ('51 %', 'du fichier porte le même libellé « Services »', BAD),
    ('34', 'entreprises affichent 5,0/5 sur 3 avis ou moins', WARN),
    ('59', 'sites web encore en http:// et non https://', WARN),
    ('18', 'fiches sans catégorie, sans note et sans avis', WARN),
    ('1', 'entreprise en double, et 1 géolocalisée hors de Marrakech', MUTED),
]):
    y = 2.55 + i * 0.72
    text(s, n, M + 6.9, y, 0.95, 0.4, size=20, bold=True, color=c, valign='middle')
    text(s, t, M + 7.9, y - 0.04, 4.2, 0.52, size=12, valign='middle', spacing=1.1)
notes(s, "Première étape : mesurer, sans rien corriger. Le script sort un profil complet. Trois constats comptent. Un : la moitié du fichier n'a pas d'email. Deux : la catégorie de Google est inutilisable, « Services » couvre la moitié des lignes. Trois : la note moyenne de 4,67 est trompeuse, parce que 34 entreprises ont un 5 sur 5 obtenu sur trois avis ou moins. Ces trois constats dictent le nettoyage.")

# ==================================================================== 10
s = content('Données', 'Nettoyage : problèmes détectés et solutions',
            '02_clean.py — chaque correction est comptée et journalisée dans cleaning_report.json')
card(s, M, 1.85, COL, 4.55, name='tableau')
text(s, 'Problème détecté', M + 0.3, 2.0, 4.4, 0.3, size=12, bold=True, color=ACCENT)
text(s, 'Solution appliquée en Python', M + 4.85, 2.0, 5.6, 0.3, size=12, bold=True, color=ACCENT)
text(s, 'Lignes', M + 10.6, 2.0, 1.0, 0.3, size=12, bold=True, color=ACCENT, align='right')
for i, (p, sol, n) in enumerate([
    ('Fichier UTF-8 avec BOM', 'Lecture en utf-8-sig, sinon la 1re colonne devient illisible', '—'),
    ('Téléphones en +212, 00212, espacements variables', 'Normalisation en 0X XX XX XX XX', '1'),
    ('Impossible de savoir qui est sur WhatsApp', 'Indicateur mobile déduit des préfixes 06/07', '196'),
    ('URLs incohérentes (http, majuscules, slash final)', 'Normalisation https, hôte en minuscules', '213'),
    ('nombre_avis vide', '0 avis — une absence, pas une inconnue', '18'),
    ('Note vide', 'Laissée vide volontairement : rien à imputer', '18'),
    ('5,0/5 sur 2 avis pèse autant qu’un 4,6 sur 900', 'Note bayésienne (n·note + 12·moyenne)/(n+12)', '34'),
    ('« Services » = 51 % du fichier', 'Secteur re-dérivé du nom quand le libellé est générique', '88'),
    ('Doublon et coordonnées hors zone', 'Déduplication sur nom normalisé, coordonnées à null', '2'),
]):
    y = 2.4 + i * 0.44
    text(s, p, M + 0.3, y, 4.5, 0.4, size=12, color=INK, valign='middle')
    text(s, sol, M + 4.85, y, 5.65, 0.4, size=12, valign='middle')
    text(s, n, M + 10.6, y, 1.0, 0.4, size=12, bold=True, color=ACCENT, align='right', valign='middle')
text(s, '283 lignes en entrée → 282 lignes et 21 colonnes en sortie', M, 6.55, COL - 1.1, 0.4, size=13.5, bold=True, color=INK)
notes(s, "Voici le cœur de la partie Python. Chaque ligne est un problème que j'ai mesuré à l'étape 1, et la correction en face. Deux décisions que je veux défendre. D'abord, je ne remplace jamais une note manquante par la moyenne : une note inventée se propagerait dans le score et fausserait le classement des prospects. Un champ vide reste vide. Ensuite, la note bayésienne : je tire chaque note vers la moyenne en proportion du peu d'avis qui la soutiennent.")

# ==================================================================== 11
s = content('Données', 'Le résultat du nettoyage', 'Des champs exploitables, et une note qui reflète la quantité de preuve')
image(s, FIG('04_completeness'), M, 1.9, C2, 2.45)
image(s, FIG('05_rating_adjustment'), RIGHT, 1.9, C2, 2.45)
card(s, M, 4.6, C2, 1.95, name='c1')
text(s, 'Le secteur passe de 94 % à 100 %', M + 0.28, 4.78, C2 - 0.56, 0.35, size=15, bold=True, color=INK)
text(s, '88 entreprises étiquetées « Services » ont retrouvé un métier lisible, déduit de leur nom. La segmentation par secteur devient possible.',
     M + 0.28, 5.16, C2 - 0.56, 1.1, size=12.5, spacing=1.15)
card(s, RIGHT, 4.6, C2, 1.95, fill=SOFT, line='CFE2F7', name='c2')
text(s, 'Corrélation note / avis : −0,32', RIGHT + 0.28, 4.78, C2 - 0.56, 0.35, size=15, bold=True, color=INK)
text(s, 'Plus une entreprise a d’avis, plus sa note baisse. C’est la preuve empirique que les 5,0 parfaits viennent d’échantillons minuscules — et la justification de la pondération.',
     RIGHT + 0.28, 5.16, C2 - 0.56, 1.1, size=12.5, spacing=1.15)
notes(s, "À gauche, l'effet du nettoyage sur la complétude. À droite, l'effet de la pondération : les points gris sont les notes brutes, les bleus les notes ajustées, et on voit les 5,0 sur très peu d'avis redescendre. Le chiffre que je retiens, c'est la corrélation de −0,32 entre le nombre d'avis et la note : plus une entreprise est évaluée, plus sa note baisse. Ce n'est pas une intuition, c'est mesuré, et ça valide la correction.")

# ==================================================================== 12
s = content('Données', 'Analyse : qui est réellement joignable', 'Le premier résultat exploitable — et il contredit l’intuition')
image(s, FIG('06_funnel'), M, 1.95, 7.3, 3.5)
card(s, M + 7.7, 1.95, COL - 7.7, 3.5, name='lecture')
text(s, 'Ce que ça change', M + 8.0, 2.15, 3.85, 0.38, size=18, bold=True, color=INK)
bullets(s, M + 8.0, 2.65, 3.85, 2.6, [
    'Le téléphone couvre 97 % du fichier, l’email seulement 50 %',
    '70 % ont un numéro mobile : WhatsApp touche plus de monde que l’email',
    'Une plateforme centrée sur l’email seul rate la moitié du marché',
    'D’où les boutons Appel, WhatsApp et Email côte à côte dans l’interface',
], 12.5)
stat(s, M, 5.65, 2.95, '97 %', 'joignables par téléphone', GOOD, 1.2)
stat(s, M + 3.15, 5.65, 2.95, '70 %', 'joignables sur WhatsApp', ACCENT, 1.2)
stat(s, M + 6.3, 5.65, 2.95, '50 %', 'joignables par email', BAD, 1.2)
stat(s, M + 9.45, 5.65, 2.44, '274', 'contactables au total', GOOD, 1.2)
notes(s, "Premier résultat d'analyse. L'entonnoir montre que si on ne compte que l'email, on perd la moitié du fichier. Mais 97 % ont un téléphone et 70 % un mobile, donc joignables sur WhatsApp. C'est une conclusion qui a directement changé le produit : l'interface met Appel, WhatsApp et Email au même niveau, au lieu de tout miser sur l'email.")

# ==================================================================== 13
s = content('Données', 'Analyse : où se trouve l’opportunité', 'Déficit de présence en ligne par secteur, et popularité très inégale')
image(s, FIG('07_digital_gap'), M, 1.9, C2, 3.4)
image(s, FIG('08_reviews_distribution'), RIGHT, 1.9, C2, 3.4)
card(s, M, 5.5, C2, 1.45, name='i1')
text(s, '22 % n’ont aucun site web', M + 0.28, 5.63, C2 - 0.56, 0.32, size=14.5, bold=True, color=INK)
text(s, 'La proportion monte à 50 % chez les consultants : un besoin réel, et un angle d’approche concret.',
     M + 0.28, 5.97, C2 - 0.56, 0.82, size=12.5, spacing=1.12)
card(s, RIGHT, 5.5, C2, 1.45, name='i2')
text(s, 'Médiane 18 avis, moyenne 281', RIGHT + 0.28, 5.63, C2 - 0.56, 0.32, size=14.5, bold=True, color=INK)
text(s, 'Distribution log-normale : quelques géants (jusqu’à 6 857 avis) et une longue traîne. La moyenne ne veut rien dire ici.',
     RIGHT + 0.28, 5.97, C2 - 0.56, 0.82, size=12.5, spacing=1.12)
notes(s, "Deux analyses. À gauche, le déficit digital par secteur : 22 % des entreprises n'ont aucun site, et ça monte à la moitié chez les consultants. À droite, la distribution des avis en échelle logarithmique : médiane 18, moyenne 281, maximum 6 857. C'est une distribution log-normale, donc la moyenne n'a aucun sens — et c'est pourquoi le score utilise un logarithme du nombre d'avis plutôt que le nombre brut.")

# ==================================================================== 14
s = content('Données', 'Du dataset au score d’opportunité', 'Quatre facteurs pondérés, la même formule en Python et dans l’application')
image(s, FIG('09_score_distribution'), M, 1.9, 5.9, 3.2)
image(s, FIG('10_map'), M + 6.3, 1.9, 3.5, 3.2)
card(s, M + 10.0, 1.9, COL - 10.0, 3.2, fill=SOFT, line='CFE2F7', name='formule')
text(s, 'Les 4 facteurs', M + 10.22, 2.05, 1.62, 0.4, size=13.5, bold=True, color=INK)
for i, (k, v) in enumerate([('Secteur', '30'), ('Absence\nde site', '30'), ('Volume\nd’avis', '25'), ('Joignabilité', '15')]):
    y = 2.46 + i * 0.62
    text(s, k, M + 10.22, y, 1.02, 0.56, size=11.5, valign='middle', spacing=1.05)
    text(s, v, M + 11.24, y, 0.45, 0.56, size=14.5, bold=True, color=ACCENT, align='right', valign='middle')
stat(s, M, 5.35, 3.0, '68', 'prospects prioritaires (score ≥ 65)', GOOD, 1.3)
stat(s, M + 3.2, 5.35, 3.0, '55,6', 'score moyen sur 282 entreprises', ACCENT, 1.3)
card(s, M + 6.4, 5.35, COL - 6.4, 1.3, name='usage')
text(s, 'Le score n’est pas décoratif : il ordonne la page « Aujourd’hui », le tableau des entreprises et le tableau de bord. L’utilisateur ne choisit pas par où commencer — la donnée le fait.',
     M + 6.7, 5.52, 5.15, 1.0, size=12.5, valign='middle', spacing=1.15)
notes(s, "Toute l'analyse converge vers un seul chiffre : le score d'opportunité, de 0 à 100, construit sur quatre facteurs pondérés. 68 entreprises dépassent 65, ce sont les prospects prioritaires. La carte montre leur répartition dans Marrakech, la couleur étant le score. Et surtout, ce score pilote réellement l'interface : il décide quelles entreprises apparaissent en premier.")

# ==================================================================== 15
s = section_slide('Plateforme', 'La plateforme', 'Frontend, fonctionnalités et intelligence artificielle')
chip(s, M, 2.42, 'PARTIE 3', 'info', 1.5)
notes(s, 'Je passe maintenant à la plateforme elle-même.')

# ==================================================================== 16
s = content('Plateforme', 'Frontend et intégration avec le backend',
            'React 19 + Vite + Tailwind — 37 modules, 3 040 lignes, un seul fichier CSS')
card(s, M, 1.9, 6.2, 4.3, name='struct')
text(s, 'Une structure par responsabilité', M + 0.3, 2.08, 5.5, 0.38, size=17, bold=True, color=INK)
for i, (k, v) in enumerate([
    ('lib/', 'client API, scoring, formatage — sans React'),
    ('store/', 'AppContext : entreprises, réglages, tâches'),
    ('components/ui/', 'Button, Card, Pill, DataTable, Drawer'),
    ('components/charts/', 'Chart.js encapsulé, vue graphique/tableau'),
    ('features/lead/', 'le panneau entreprise, un fichier par bloc'),
    ('pages/', 'un fichier par route'),
]):
    y = 2.58 + i * 0.56
    text(s, k, M + 0.3, y, 1.9, 0.45, size=12.5, bold=True, color=ACCENT, valign='middle')
    text(s, v, M + 2.25, y, 3.8, 0.45, size=12, valign='middle', spacing=1.1)
card(s, M + 6.6, 1.9, COL - 6.6, 4.3, name='integ')
text(s, 'Comment il parle au backend', M + 6.9, 2.08, 5.2, 0.38, size=17, bold=True, color=INK)
bullets(s, M + 6.9, 2.58, 5.2, 2.0, [
    'Un seul client HTTP (lib/api.js) : toutes les routes y sont déclarées',
    'Un seul état global (AppContext) : aucune page ne refait un appel déjà fait',
    'Le score est calculé côté client à partir des données brutes, donc instantané quand on bouge un curseur',
    'Vite construit en 1,8 s ; Flask sert le dossier dist et renvoie index.html sur toutes les routes',
], 12.5)
card(s, M + 6.9, 4.85, 5.2, 1.1, fill=SOFT, line='CFE2F7', name='theme')
text(s, 'Thème : un seul fichier', M + 7.15, 4.97, 4.7, 0.3, size=13, bold=True, color=INK)
text(s, 'Les couleurs sont des variables CSS redéfinies en mode sombre : aucun composant ne teste le thème.',
     M + 7.15, 5.28, 4.7, 0.6, size=11.5, spacing=1.1)
notes(s, "Le frontend est découpé par responsabilité. Deux choix à défendre. Un : un seul client HTTP et un seul état global, donc pas d'appels dupliqués entre les pages. Deux : le score est recalculé côté navigateur à partir des données brutes. Ça veut dire que quand l'utilisateur déplace un curseur de pondération dans les réglages, tous les classements se recalculent instantanément, sans aller-retour serveur.")

# ==================================================================== 17
s = content('Plateforme', 'Les fonctionnalités principales', 'Sept écrans, de la vue d’ensemble à l’envoi, au suivi et à l’administration')
w = (COL - 0.3 * 3) / 4
for i, (t, b) in enumerate([
    ('Tableau de bord', 'KPI et 4 graphiques Chart.js, filtrables par secteur et statut. Chaque graphique a une vue tableau.'),
    ('Aujourd’hui', 'Les relances dues en premier, puis les meilleurs prospects du jour classés par score.'),
    ('Entreprises', 'Les 283 fiches : recherche, filtres, tri et export CSV. Le jeu de données est livré avec l’application.'),
    ('Pipeline', 'Tableau kanban : chaque colonne défile seule, le plateau défile horizontalement.'),
    ('Panneau entreprise', 'Contact, score détaillé, rédaction IA, envoi, journal des contacts, audit du site.'),
    ('Réglages', 'Identité, plafond d’envoi, clé IA, pondérations du score avec leur effet en direct.'),
    ('Admin', 'Réservé aux administrateurs : comptes, droits, inscriptions, et correction des fiches entreprise.'),
]):
    x = M + (i % 4) * (w + 0.3)
    y = 1.95 + (i // 4) * 2.45
    card(s, x, y, w, 2.25, name=f'feat-{i}')
    text(s, t, x + 0.22, y + 0.18, w - 0.44, 0.38, size=14.5, bold=True, color=ACCENT)
    text(s, b, x + 0.22, y + 0.6, w - 0.44, 1.5, size=11.5, spacing=1.15)
# the eighth slot carries the rule that ties the screens together
lx, ly = M + 3 * (w + 0.3), 1.95 + 2.45
card(s, lx, ly, w, 2.25, fill=SOFT, line='CFE2F7', name='feat-regle')
text(s, 'La règle transversale', lx + 0.22, ly + 0.18, w - 0.44, 0.38, size=14.5, bold=True, color=INK)
text(s, 'Enregistrer un contact fait avancer le statut tout seul et propose une date de relance, pour qu’aucun échange ne se perde.',
     lx + 0.22, ly + 0.6, w - 0.44, 1.5, size=11.5, spacing=1.15)
notes(s, "Sept écrans. Celle que j'utilise le plus est « Aujourd'hui » : elle répond à la seule question qui compte le matin, par où je commence. Les relances dues d'abord, puis les meilleurs prospects par score. Et le détail qui fait la différence à l'usage : quand j'enregistre un appel avec le résultat « intéressé », le statut passe à « répondu » et une date de relance est proposée automatiquement.")

# ==================================================================== 18
s = content('Plateforme', 'L’intégration de l’intelligence artificielle', 'Google Gemini 2.5 Flash, avec une clé propre à chaque utilisateur')
card(s, M, 1.9, 6.0, 2.4, name='ia1')
chip(s, M + 0.28, 2.1, 'USAGE 1', 'info', 1.2)
text(s, 'Rédaction de la candidature', M + 0.28, 2.52, 5.4, 0.38, size=17, bold=True, color=INK)
text(s, 'Le modèle reçoit uniquement des faits : le profil de l’utilisateur et la fiche de l’entreprise. Il lui est interdit d’inventer un client, un résultat ou un contact commun. Il ne rédige ni signature ni mention de désinscription — l’application les ajoute elle-même.',
     M + 0.28, 2.95, 5.4, 1.25, size=12.5, spacing=1.15)
card(s, M + 6.4, 1.9, COL - 6.4, 2.4, name='ia2')
chip(s, M + 6.68, 2.1, 'USAGE 2', 'good', 1.2)
text(s, 'Assistant intégré « Ask »', M + 6.68, 2.52, 5.4, 0.38, size=17, bold=True, color=INK)
text(s, 'Il répond aux questions sur l’application. Sa mémoire tient en trois couches : un guide écrit de la plateforme, un instantané des chiffres de l’utilisateur, et l’historique de la conversation conservé côté serveur.',
     M + 6.68, 2.95, 5.4, 1.25, size=12.5, spacing=1.15)
card(s, M, 4.55, COL, 2.0, fill=SOFT, line='CFE2F7', name='ia3')
text(s, 'Les garde-fous', M + 0.3, 4.72, 4, 0.35, size=16, bold=True, color=INK)
gw = (COL - 0.6 - 0.3 * 3) / 4
for i, (t, b) in enumerate([
    ('Clé par utilisateur', 'Chacun saisit sa propre clé Gemini. Elle est vérifiée auprès de Google avant d’être acceptée.'),
    ('Chiffrée au repos', 'AES-256-GCM. Elle n’est jamais renvoyée au navigateur, même à son propriétaire.'),
    ('Dégradation propre', 'Sans clé, l’application fonctionne : la rédaction retombe sur un modèle de texte.'),
    ('Jamais d’envoi auto', 'L’IA propose un brouillon. L’envoi reste un geste humain, explicite.'),
]):
    x = M + 0.3 + i * (gw + 0.3)
    text(s, t, x, 5.12, gw, 0.3, size=13, bold=True, color=ACCENT)
    text(s, b, x, 5.44, gw, 0.95, size=11.5, spacing=1.12)
notes(s, "L'IA sert à deux choses. Rédiger la candidature, et répondre aux questions sur l'application. Le point que je veux défendre, c'est le choix du « bring your own key » : chaque utilisateur saisit sa propre clé Gemini, elle est validée auprès de Google, chiffrée en AES-256 avant stockage, et jamais renvoyée au navigateur. Et sans clé, l'application continue de marcher. L'IA est une amélioration, pas une dépendance.")

# ==================================================================== 19
s = content('Conclusion', 'Les résultats obtenus', 'Une chaîne complète, de la donnée brute à la candidature envoyée')
w = (COL - 0.3 * 4) / 5
for i, (v, l) in enumerate([('283', 'entreprises\ncollectées'), ('282', 'lignes propres\n21 colonnes'),
                            ('68', 'prospects\nprioritaires'), ('36', 'endpoints\nREST'), ('15', 'tests\nautomatisés')]):
    x = M + i * (w + 0.3)
    card(s, x, 1.95, w, 1.55)
    text(s, v, x + 0.2, 2.1, w - 0.4, 0.6, size=32, bold=True, color=ACCENT, align='center', valign='middle')
    text(s, l, x + 0.2, 2.72, w - 0.4, 0.65, size=11.5, align='center', spacing=1.1)
card(s, M, 3.78, 6.1, 2.6, name='acquis')
text(s, 'Ce qui fonctionne', M + 0.3, 3.96, 5.4, 0.35, size=17, bold=True, color=GOOD)
bullets(s, M + 0.3, 4.42, 5.4, 1.85, [
    'La chaîne Python est reproductible : trois scripts, trois rapports JSON',
    'Les graphiques des slides et ceux de l’application viennent du même calcul',
    'Les règles d’envoi sont testées : plafond, doublons, désinscription',
    'L’application est utilisable sans clé IA et sans serveur mail',
], 12.5)
card(s, M + 6.5, 3.78, COL - 6.5, 2.6, name='limites')
text(s, 'Les limites, assumées', M + 6.8, 3.96, 5.4, 0.35, size=17, bold=True, color=BAD)
bullets(s, M + 6.8, 4.42, 5.4, 1.85, [
    'La moitié des entreprises reste sans email : le téléphone prend le relais',
    'Le secteur est déduit du nom par règles — rapide, mais faillible',
    'db.json ne tient pas la montée en charge au-delà de quelques milliers de fiches',
    'Les données sont une photo de Marrakech à une date, non rafraîchie',
], 12.5)
notes(s, "Les chiffres clés du projet. Ce qui fonctionne : la chaîne Python est reproductible, et les graphiques que je viens de montrer viennent du même calcul que l'application. Je tiens aussi à annoncer les limites moi-même : la moitié du fichier n'a pas d'email, le secteur est déduit par règles donc faillible, et la base fichier ne tiendra pas la montée en charge. Ce sont des choix adaptés à la taille du projet, pas des oublis.")

# ==================================================================== 20
s = content('Conclusion', 'Perspectives d’amélioration', 'Par ordre de valeur apportée')
for i, (n, t, b) in enumerate([
    ('1', 'Intégrer de vraies offres de stage', 'Brancher les sites d’annonces marocains pour croiser les offres publiées avec la base d’entreprises, et distinguer candidature spontanée et réponse à une offre.'),
    ('2', 'Passer à PostgreSQL', 'db.json atteint sa limite. Une base relationnelle apporterait le multi-utilisateur réel, les transactions et la recherche plein texte.'),
    ('3', 'Classer le secteur par apprentissage', 'Remplacer les règles sur le nom par un modèle entraîné, et mesurer sa précision au lieu de la supposer.'),
    ('4', 'Rafraîchir les données', 'Une tâche planifiée qui relance la collecte Google Places et détecte les fermetures et les changements de contact.'),
    ('5', 'Mesurer ce qui marche', 'Suivre le taux de réponse par secteur et par modèle de message, puis réinjecter ce signal dans le score.'),
]):
    y = 1.92 + i * 0.95
    card(s, M, y, COL, 0.82, name=f'persp-{n}')
    dot(s, M + 0.24, y + 0.21, n)
    text(s, t, M + 0.78, y + 0.08, 3.5, 0.66, size=14, bold=True, color=INK, valign='middle')
    text(s, b, M + 4.4, y + 0.08, COL - 4.65, 0.66, size=12, valign='middle', spacing=1.1)
notes(s, "Cinq pistes, classées par valeur. La première est la plus importante : brancher de vraies offres de stage pour croiser les annonces publiées avec ma base d'entreprises. La deuxième est technique et inévitable si le projet grandit. Et la cinquième est la plus intéressante sur le plan data : mesurer le taux de réponse réel et réinjecter ce signal dans le score, pour qu'il s'améliore avec l'usage au lieu de rester figé sur mes hypothèses de départ.")

# ==================================================================== 21
s = closing_slide('Conclusion', 'Merci')
text(s, 'Des questions ?', M, 3.85, 6, 0.5, size=20)
card(s, M, 4.75, 8.6, 1.35, name='liens')
text(s, 'Code source', M + 0.3, 4.92, 2.4, 0.3, size=12.5, bold=True, color=ACCENT)
text(s, 'github.com/slaym-13/Prospect-Suite', M + 0.3, 5.24, 2.7, 0.3, size=10.5)
text(s, 'Plateforme en ligne', M + 3.1, 4.92, 2.6, 0.3, size=12.5, bold=True, color=ACCENT)
text(s, 'https://prospect-suite-alpha.vercel.app/', M + 3.1, 5.24, 2.7, 0.3, size=10.5)
text(s, 'Démonstration', M + 5.9, 4.92, 2.4, 0.3, size=12.5, bold=True, color=ACCENT)
text(s, 'vidéo courte', M + 5.9, 5.24, 2.4, 0.3, size=12.5)
notes(s, "Merci. Je suis prêt à détailler n'importe quelle partie : le nettoyage Python, la logique métier du backend, l'organisation du frontend ou l'intégration de Gemini.")


# ------------------------------------------------------------------ finish
SLOTS = ['dk1', 'lt1', 'dk2', 'lt2', 'accent1', 'accent2', 'accent3', 'accent4', 'accent5', 'accent6', 'hlink', 'folHlink']


def apply_theme():
    """Write the deck's own palette, fonts and name into the theme, instead of Office's."""
    master = pres.slide_masters[0]
    theme_part = next(r.target_part for r in master.part.rels.values() if r.reltype.endswith('/theme'))
    root = etree.fromstring(theme_part.blob)
    root.set('name', THEME['name'])
    scheme = root.find('.//' + qn('a:clrScheme'))
    scheme.set('name', THEME['name'])
    for slot in SLOTS:
        el = scheme.find(qn(f'a:{slot}'))
        for child in list(el):
            el.remove(child)
        etree.SubElement(el, qn('a:srgbClr'), val=THEME['colors'][slot])
    fonts = root.find('.//' + qn('a:fontScheme'))
    fonts.set('name', THEME['name'])
    for kind in ('a:majorFont', 'a:minorFont'):
        fonts.find(qn(kind)).find(qn('a:latin')).set('typeface', THEME['font'])
    theme_part._blob = etree.tostring(root, xml_declaration=True, encoding='UTF-8', standalone=True)


def add_sections():
    """Group the slides into named sections, as PowerPoint shows them in the sidebar."""
    p14 = 'http://schemas.microsoft.com/office/powerpoint/2010/main'
    prs = pres.part._element
    ids = {sl.slide_id for sl in pres.slides}
    ext_lst = prs.find(qn('p:extLst'))
    if ext_lst is None:
        ext_lst = etree.SubElement(prs, qn('p:extLst'))
    ext = etree.SubElement(ext_lst, qn('p:ext'), uri='{521415D9-36F7-43E2-AB2F-B90AF26B5E84}')
    lst = etree.SubElement(ext, f'{{{p14}}}sectionLst', nsmap={'p14': p14})
    for name, slides in SECTIONS:
        sec = etree.SubElement(lst, f'{{{p14}}}section', name=name, id='{' + str(uuid.uuid4()).upper() + '}')
        sl = etree.SubElement(sec, f'{{{p14}}}sldIdLst')
        for slide in slides:
            assert slide.slide_id in ids
            etree.SubElement(sl, f'{{{p14}}}sldId', id=str(slide.slide_id))


def main():
    ap = argparse.ArgumentParser(description=__doc__.split('\n')[0])
    ap.add_argument('--out', default=os.path.join('presentation', 'deck_generated.pptx'))
    out = ap.parse_args().out
    apply_theme()
    add_sections()
    pres.save(out)
    print('wrote', out)


if __name__ == '__main__':
    main()
