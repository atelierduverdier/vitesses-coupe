#!/usr/bin/env python3
# =========================================================================
# freecad_biblio.py — lire et écrire les bibliothèques d'outils de FreeCAD
# © Atelier du Verdier — licence LGPL-2.1-or-later (cf. LICENSE).
# =========================================================================
# Ce module ne DÉPEND PAS de FreeCAD : il lit et écrit ses fichiers, qui
# sont du JSON. L'appli peut donc s'en servir sans que FreeCAD tourne, ni
# même qu'il soit installé.
#
#   CamAssets/Tools/Bit/*.fctb       un outil : géométrie seule
#   CamAssets/Tools/Library/*.fctl   une bibliothèque : une liste d'outils
#
# =========================================================================
#  POURQUOI LES VITESSES VIVENT À CÔTÉ
# =========================================================================
# Un `.fctb` a bien un champ libre `attribute`, et on pourrait croire qu'il
# suffit d'y ranger broche et avance. Mesuré le 31/08/2026 sur FreeCAD
# 1.1.3 : **FreeCAD le VIDE** dès qu'il réécrit l'outil — un aller-retour
# par le Gestionnaire de bibliothèque et tout ce qu'on y avait mis a
# disparu, sans message.
#
# Les vitesses sont donc gardées par l'appli, dans son propre fichier, et
# rattachées à l'outil par le NOM DE SON FICHIER .fctb — le seul point fixe
# qui survive à un aller-retour. Renommer un outil dans FreeCAD ne casse
# rien tant que le fichier garde son nom ; le déplacer, si.
# =========================================================================

import json
import re
import unicodedata
from pathlib import Path

DOSSIER_CONF = Path.home() / '.config' / 'vitesses-coupe'
FICHIER_VITESSES = DOSSIER_CONF / 'vitesses-freecad.json'


# --- Où FreeCAD range ses outils -----------------------------------------
def dossiers_outils():
    """Les dossiers `CamAssets/Tools` trouvés, avec de quoi les distinguer.

    Le dossier de données de FreeCAD est VERSIONNÉ (`v1-1`, `v1-2`,
    `v26-3`…) et plusieurs versions cohabitent presque toujours : une
    stable installée, une weekly essayée un jour, une ancienne oubliée.
    **Deviner lequel est le bon est un piège** — trier par date de
    modification désignait ici `v26-3`, la version de développement, alors
    que la machine tourne sur 1.1.3. On rend donc TOUT, avec le nom de
    version et le nombre d'outils, et c'est l'appli qui fait choisir.
    """
    racines = [Path.home() / '.local' / 'share' / 'FreeCAD',
               Path.home() / '.FreeCAD',
               Path.home() / 'Library' / 'Preferences' / 'FreeCAD']
    trouves, vus = [], set()
    for racine in racines:
        if not racine.is_dir():
            continue
        candidats = list(racine.glob('*/CamAssets/Tools'))
        if (racine / 'CamAssets' / 'Tools').is_dir():
            candidats.append(racine / 'CamAssets' / 'Tools')
        for tools in candidats:
            if not (tools / 'Library').is_dir() or tools in vus:
                continue
            vus.add(tools)
            version = tools.parent.parent.name
            trouves.append({
                'chemin': tools,
                'version': version if version != 'FreeCAD' else '(sans version)',
                'nb_outils': len(list((tools / 'Bit').glob('*.fctb'))),
                'nb_biblio': len(list((tools / 'Library').glob('*.fctl'))),
                'modifie': (tools / 'Library').stat().st_mtime,
            })
    # Le plus fourni d'abord : c'est celui dont on se sert vraiment.
    trouves.sort(key=lambda d: (d['nb_outils'], d['modifie']), reverse=True)
    return trouves


def _lire_json(chemin):
    try:
        return json.loads(Path(chemin).read_text(encoding='utf-8'))
    except (OSError, ValueError):
        return None


# --- Lire ----------------------------------------------------------------
def bibliotheques(dossier):
    """Les bibliothèques d'un dossier : label, chemin, nombre d'outils."""
    listes = []
    for fctl in sorted((Path(dossier) / 'Library').glob('*.fctl')):
        d = _lire_json(fctl)
        if not d:
            continue
        listes.append({
            'chemin': fctl,
            'label': d.get('label') or fctl.stem,
            'outils': d.get('tools') or [],
        })
    return listes


def _nombre(texte, defaut=0.0):
    """« 6.35 mm » -> 6.35. Les unités sont dans la chaîne, pas ailleurs."""
    if texte is None:
        return defaut
    if isinstance(texte, (int, float)):
        return float(texte)
    m = re.search(r'-?[\d.,]+', str(texte))
    if not m:
        return defaut
    try:
        return float(m.group(0).replace(',', '.'))
    except ValueError:
        return defaut


# Les formes de FreeCAD, ramenées aux quatre que l'appli connaît.
_FORMES = {
    'endmill': 'plat', 'ballend': 'boule', 'bullnose': 'torique',
    'v-bit': 'vbit', 'vbit': 'vbit', 'chamfer': 'vbit', 'engraver': 'vbit',
}


def lire_outil(chemin_fctb):
    """Un `.fctb` ramené au vocabulaire de l'appli.

    Les vitesses n'y sont PAS : un fichier d'outil FreeCAD ne porte que la
    géométrie. On rend ce qu'on trouve, et l'appli calculera le reste.
    """
    d = _lire_json(chemin_fctb)
    if not d:
        return None
    p = d.get('parameter') or {}
    forme_brute = (d.get('shape-type') or d.get('shape') or 'endmill')
    forme_brute = str(forme_brute).lower().replace('.fcstd', '').strip()
    outil = {
        'fichier': Path(chemin_fctb).name,
        'name': d.get('name') or Path(chemin_fctb).stem,
        'd': _nombre(p.get('Diameter'), 6),
        'z': int(_nombre(p.get('Flutes'), 2)) or 2,
        'fz': _nombre(p.get('Chipload'), 0) or None,
        'forme': _FORMES.get(forme_brute, 'plat'),
        'hcoupe': _nombre(p.get('CuttingEdgeHeight'), 0) or None,
        'lgtotale': _nombre(p.get('Length'), 0) or None,
        'queue': _nombre(p.get('ShankDiameter'), 0) or None,
    }
    if 'CornerRadius' in p:
        outil['extra'] = _nombre(p.get('CornerRadius'), 0) or None
    elif 'CuttingEdgeAngle' in p:
        outil['extra'] = _nombre(p.get('CuttingEdgeAngle'), 0) or None
    return outil


def outils_de(dossier, bibliotheque):
    """Les outils d'une bibliothèque, lus depuis ses `.fctb`."""
    bit = Path(dossier) / 'Bit'
    liste = []
    for entree in bibliotheque['outils']:
        chemin = bit / str(entree.get('path', ''))
        if not chemin.is_file():
            continue
        o = lire_outil(chemin)
        if o:
            o['nr'] = entree.get('nr')
            liste.append(o)
    return liste


# --- Les vitesses, gardées à côté ---------------------------------------
def vitesses_connues():
    """Ce que l'appli sait des outils de FreeCAD : nom de fichier -> vitesses."""
    d = _lire_json(FICHIER_VITESSES)
    return d if isinstance(d, dict) else {}


def retenir_vitesses(nom_fichier, vitesses):
    """Associe des vitesses à un `.fctb`, hors des fichiers de FreeCAD."""
    tout = vitesses_connues()
    tout[nom_fichier] = vitesses
    try:
        DOSSIER_CONF.mkdir(parents=True, exist_ok=True)
        FICHIER_VITESSES.write_text(
            json.dumps(tout, ensure_ascii=False, indent=2), encoding='utf-8')
    except OSError:
        pass
    return tout


# --- Écrire --------------------------------------------------------------
def _nom_de_fichier(nom):
    """Un nom de fichier sûr, tiré du nom de l'outil."""
    sans_accent = ''.join(
        c for c in unicodedata.normalize('NFD', nom)
        if unicodedata.category(c) != 'Mn')
    propre = re.sub(r'[^A-Za-z0-9]+', '_', sans_accent).strip('_')
    return (propre or 'outil') + '.fctb'


def _nom_libre(bit, nom_fichier, nom_outil):
    """Le nom sous lequel écrire, sans écraser un AUTRE outil.

    `_nom_de_fichier` ramène « Essai · Ø6,35 » et « Essai - Ø6.35 » au même
    `Essai_6_35.fctb`, et un outil nommé « 5mm Endmill » tomberait sur la
    fraise d'origine de FreeCAD. Un fichier qui existe déjà n'est donc
    réécrit que s'il porte le MÊME nom d'outil — c'est alors une mise à
    jour ; sinon on numérote : `_2`, `_3`…
    """
    racine = nom_fichier[:-len('.fctb')]
    candidat, rang = nom_fichier, 1
    while (bit / candidat).is_file():
        existant = _lire_json(bit / candidat) or {}
        if existant.get('name') == nom_outil:
            return candidat
        rang += 1
        candidat = '%s_%d.fctb' % (racine, rang)
    return candidat


def ecrire_outil(dossier, fichier_outil_json, bibliotheque=None, vitesses=None):
    """Écrit un `.fctb` et l'inscrit dans une bibliothèque.

    Rend le nom du fichier écrit — qui peut être numéroté si un autre outil
    occupait déjà ce nom, cf. `_nom_libre`. Si `bibliotheque` est donnée,
    l'outil est ajouté à son `.fctl` — c'est ce qui le fait apparaître dans
    le Gestionnaire de bibliothèque de FreeCAD. `vitesses` est retenu à
    côté, puisque le fichier d'outil ne sait pas les garder.
    """
    dossier = Path(dossier)
    bit = dossier / 'Bit'
    bit.mkdir(parents=True, exist_ok=True)
    nom_outil = fichier_outil_json.get('name', 'outil')
    nom_fichier = _nom_libre(bit, _nom_de_fichier(nom_outil), nom_outil)
    (bit / nom_fichier).write_text(
        json.dumps(fichier_outil_json, ensure_ascii=False, indent=2) + '\n',
        encoding='utf-8')

    if bibliotheque is not None:
        d = _lire_json(bibliotheque['chemin']) or {'label': bibliotheque['label'],
                                                   'tools': [], 'version': 1}
        outils = d.get('tools') or []
        # Un même fichier ne s'inscrit pas deux fois : on met à jour.
        if not any(t.get('path') == nom_fichier for t in outils):
            # Un `nr` absent ou nul ne doit pas faire tomber `max`.
            numeros = [t.get('nr') for t in outils
                       if isinstance(t.get('nr'), (int, float))
                       and not isinstance(t.get('nr'), bool)]
            outils.append({'nr': (max(numeros) + 1) if numeros else 1,
                           'path': nom_fichier})
            d['tools'] = outils
            Path(bibliotheque['chemin']).write_text(
                json.dumps(d, ensure_ascii=False, indent=2) + '\n',
                encoding='utf-8')

    if vitesses:
        retenir_vitesses(nom_fichier, vitesses)
    return nom_fichier
