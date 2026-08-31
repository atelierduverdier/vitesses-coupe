#!/usr/bin/env python3
# =========================================================================
# carnet_noyau.py — le carnet d'essais d'usinage, sans interface
# © Atelier du Verdier — licence LGPL-2.1-or-later (cf. LICENSE).
# =========================================================================
# `coupe_noyau.py` calcule la théorie ; ce module retient ce que la matière
# a RÉPONDU. Un essai, c'est la matière telle qu'elle était, la fraise telle
# qu'elle est, les vitesses réellement tenues, une photo du résultat et un
# verdict court. C'est le pendant fraiseuse du nuancier laser : on usine une
# fois, on note, et la fois suivante on consulte AVANT de calculer.
#
# Trois décisions à connaître avant de bâtir une interface dessus :
#   1. Le carnet vit HORS du dépôt (mesures d'atelier, pas des sources —
#      même règle que la bibliothèque d'outils, cf. .gitignore) : par défaut
#      dans ~/Projets/machine/carnet-essais, avec les affaires de la machine.
#   2. Un carnet illisible n'est JAMAIS écrasé : `charger` lève, donc tout
#      ce qui écrit lève aussi. Perdre des verdicts d'établi pour un fichier
#      abîmé serait le vrai dégât ; l'écriture passe par un .tmp + replace.
#   3. La théorie n'est PAS figée dans l'essai : `comparer_theorie` la
#      recalcule à la demande. L'essai est la mesure ; le noyau de calcul,
#      lui, peut s'affiner sans salir l'historique.
# =========================================================================

import datetime
import json
import os
import shutil
import unicodedata
from pathlib import Path

import coupe_noyau as C

DOSSIER_DEFAUT = Path.home() / 'Projets' / 'machine' / 'carnet-essais'
FICHIER_CARNET = 'carnet.json'
SOUS_DOSSIER_PHOTOS = 'photos'

# Les champs d'un essai, dans l'ordre où le JSON les montre. `id` et `photo`
# n'y sont pas : le carnet les pose lui-même, personne ne les saisit.
#   d, z          : la fraise en chiffres (Ø mm, dents) — d est OBLIGATOIRE,
#                   un essai sans Ø ne se retrouve jamais à la consultation.
#   n, vf, ap, ae : broche tr/min, avance mm/min, passes mm. Ici `ap` est la
#                   passe RÉELLE en mm, pas la fourchette-texte des matières.
#   0 signifie « non renseigné » : aucune de ces grandeurs ne peut être nulle.
CHAMPS_ESSAI = ('date', 'matiere', 'essence', 'operation', 'travail',
                'fraise', 'd', 'z', 'n', 'vf', 'ap', 'ae', 'verdict', 'note')

# Suggestions pour une liste déroulante — le champ reste du texte libre.
OPERATIONS = ['Rainure', 'Contour', 'Poche', 'Surfaçage', 'Perçage', 'Gravure']


def nouvel_essai(matiere='', essence='', operation='', travail='', fraise='',
                 d='', z='', n='', vf='', ap='', ae='',
                 verdict='', note='', date=''):
    """Un essai normalisé, prêt à être ajouté au carnet.

    Les nombres passent par `coupe_noyau.num` (virgule et espaces acceptés).
    La matière, si elle est donnée, doit être un identifiant du noyau —
    c'est elle qui permet de comparer à la théorie et de filtrer ; le bois
    précis (« chêne de récup », « douglas purgé ») va dans `essence`, en
    texte libre. Le verdict peut rester vide : on règle, on usine, on
    regarde — et on complète après coup.
    """
    matiere = str(matiere or '').strip()
    if matiere and matiere not in C.PAR_ID:
        raise ValueError("Matière inconnue du noyau : « %s ». Valides : %s."
                         % (matiere, ', '.join(sorted(C.PAR_ID))))
    d = C.num(d, 0.0)
    if not d:
        raise ValueError("Il faut le diamètre de la fraise : un essai sans Ø "
                         "ne peut pas être consulté.")
    date = str(date or '').strip()
    date = (datetime.date.fromisoformat(date) if date
            else datetime.date.today()).isoformat()
    return dict(
        id='', date=date, matiere=matiere,
        essence=str(essence or '').strip(),
        operation=str(operation or '').strip(),
        travail=str(travail or '').strip(),
        fraise=str(fraise or '').strip(),
        d=d, z=int(round(C.num(z, 0.0))),
        n=C.num(n, 0.0), vf=C.num(vf, 0.0),
        ap=C.num(ap, 0.0), ae=C.num(ae, 0.0),
        verdict=str(verdict or '').strip(),
        note=str(note or '').strip(),
        photo='',
    )


# --- Le carnet sur le disque ---------------------------------------------

def charger(dossier=None):
    """Tous les essais du carnet. Pas de carnet : liste vide.

    Un carnet ILLISIBLE, en revanche, lève — jamais de liste vide de
    complaisance, qui serait réécrite par-dessus les verdicts au premier
    ajout venu.
    """
    chemin = Path(dossier or DOSSIER_DEFAUT) / FICHIER_CARNET
    if not chemin.exists():
        return []
    essais = json.loads(chemin.read_text(encoding='utf-8'))
    if not isinstance(essais, list):
        raise ValueError("%s ne contient pas une liste d'essais." % chemin)
    return essais


def enregistrer(essais, dossier=None):
    """Écrit le carnet entier, en deux temps : .tmp puis remplacement.

    Une coupure en pleine écriture laisse l'ancien carnet intact.
    """
    dossier = Path(dossier or DOSSIER_DEFAUT)
    dossier.mkdir(parents=True, exist_ok=True)
    provisoire = dossier / (FICHIER_CARNET + '.tmp')
    provisoire.write_text(json.dumps(essais, ensure_ascii=False, indent=2)
                          + '\n', encoding='utf-8')
    os.replace(provisoire, dossier / FICHIER_CARNET)


def ajouter(essai, photo=None, dossier=None):
    """Ajoute un essai au carnet et rend l'essai tel qu'enregistré.

    L'essai repasse par `nouvel_essai` quoi qu'il arrive : un dictionnaire
    bâti à la main est normalisé pareil, et un champ que le carnet ne
    connaît pas est refusé — c'est une faute de frappe qui allait se perdre.
    `photo` est un chemin vers l'image à copier dans le carnet ; elle prend
    le nom de l'essai, l'original n'est pas touché.
    """
    essais = charger(dossier)
    en_trop = set(essai) - set(CHAMPS_ESSAI) - {'id', 'photo'}
    if en_trop:
        raise ValueError("Champs inconnus du carnet : %s."
                         % ', '.join(sorted(en_trop)))
    propre = nouvel_essai(**{c: essai.get(c, '') for c in CHAMPS_ESSAI})
    propre['id'] = _nouvel_id(essais, propre['date'])
    if photo:
        _copier_photo(propre, photo, dossier)
    essais.append(propre)
    enregistrer(essais, dossier)
    return propre


def completer(ide, photo=None, dossier=None, **champs):
    """Corrige ou complète un essai existant — le verdict vient souvent
    après coup, la photo aussi. Mêmes règles de normalisation qu'à l'ajout.
    """
    essais = charger(dossier)
    for rang, essai in enumerate(essais):
        if essai.get('id') == ide:
            break
    else:
        raise KeyError("Aucun essai « %s » dans le carnet." % ide)
    en_trop = set(champs) - set(CHAMPS_ESSAI)
    if en_trop:
        raise ValueError("Champs inconnus du carnet : %s."
                         % ', '.join(sorted(en_trop)))
    fusion = {c: essai.get(c, '') for c in CHAMPS_ESSAI}
    fusion.update(champs)
    propre = nouvel_essai(**fusion)
    propre['id'], propre['photo'] = essai['id'], essai.get('photo', '')
    if photo:
        _copier_photo(propre, photo, dossier)
    essais[rang] = propre
    enregistrer(essais, dossier)
    return propre


def supprimer(ide, dossier=None):
    """Retire un essai du carnet, photo comprise. Rend l'essai retiré."""
    essais = charger(dossier)
    restants = [e for e in essais if e.get('id') != ide]
    if len(restants) == len(essais):
        raise KeyError("Aucun essai « %s » dans le carnet." % ide)
    parti = next(e for e in essais if e.get('id') == ide)
    chemin = chemin_photo(parti, dossier)
    if chemin and chemin.is_file():
        chemin.unlink()
    enregistrer(restants, dossier)
    return parti


def chemin_photo(essai, dossier=None):
    """Le chemin de la photo de l'essai, ou None s'il n'en a pas.

    Le chemin est rendu tel quel, sans garantie que le fichier existe
    encore : c'est à l'interface de montrer un cadre vide, pas de planter.
    """
    if not essai.get('photo'):
        return None
    return Path(dossier or DOSSIER_DEFAUT) / SOUS_DOSSIER_PHOTOS / essai['photo']


def _nouvel_id(essais, date):
    """`2026-08-31-2` : la date du jour de l'essai, puis un rang. Lisible
    dans le JSON comme dans le nom de la photo."""
    rangs = [_rang(e) for e in essais
             if str(e.get('id', '')).startswith(date + '-')]
    return '%s-%d' % (date, max(rangs, default=0) + 1)


def _rang(essai):
    """Le rang dans la journée, lu au bout de l'identifiant."""
    try:
        return int(str(essai.get('id', '')).rsplit('-', 1)[-1])
    except ValueError:
        return 0


def _copier_photo(essai, source, dossier=None):
    """Copie la photo dans le carnet sous le nom de l'essai. Reprendre une
    photo remplace l'ancienne, même si l'extension change."""
    source = Path(source)
    if not source.is_file():
        raise ValueError("Photo introuvable : %s" % source)
    photos = Path(dossier or DOSSIER_DEFAUT) / SOUS_DOSSIER_PHOTOS
    photos.mkdir(parents=True, exist_ok=True)
    nom = essai['id'] + source.suffix.lower()
    shutil.copy2(source, photos / nom)
    ancien = essai.get('photo')
    if ancien and ancien != nom and (photos / ancien).is_file():
        (photos / ancien).unlink()
    essai['photo'] = nom


# --- La consultation ------------------------------------------------------

def chercher(essais, matiere=None, d=None, texte=None):
    """Les essais qui éclairent le travail qui vient, les plus parlants
    en tête.

    `matiere` filtre (identifiant du noyau) ; `d` ne filtre PAS : un essai
    en Ø8 renseigne un peu un travail en Ø6, il passe juste après — tri par
    proximité de diamètre, puis du plus récent au plus ancien. `texte`
    cherche dans tous les champs libres, sans se soucier de la casse ni des
    accents : « chene » trouve le chêne depuis l'établi.
    """
    d = C.num(d, 0.0)
    aiguille = _plat(texte) if texte else ''
    gardes = []
    for e in essais:
        if matiere and e.get('matiere') != matiere:
            continue
        if aiguille:
            botte = ' '.join(str(e.get(c, '')) for c in CHAMPS_ESSAI)
            if aiguille not in _plat(botte):
                continue
        gardes.append(e)
    gardes.sort(key=lambda e: (e.get('date', ''), _rang(e)), reverse=True)
    if d:
        # Tri stable : à distance égale, le plus récent reste devant.
        gardes.sort(key=lambda e: abs(C.num(e.get('d'), 0.0) - d))
    return gardes


def comparer_theorie(essai, **machine):
    """Ce que `coupe_noyau` aurait conseillé pour cet essai, et l'écart
    du réel — le chaînon entre l'appli et le carnet.

    Rend None sans matière connue du noyau : comparer à une théorie de
    repli serait comparer à rien. Sans nombre de dents, pas d'avance
    théorique non plus (Vf = N × Z × fz), la broche conseillée reste.
    Le nombre qui parle le plus est `rapport_copeau` : le copeau réellement
    pris, en part du conseillé — 0,13, c'est la fraise qui frotte.
    `machine` passe tel quel à `calculer` (m_min, m_max, vf_max…).
    """
    if essai.get('matiere') not in C.PAR_ID or not essai.get('d'):
        return None
    z = int(essai.get('z') or 0)
    theorie = C.calculer(essai['matiere'], d=essai['d'], z=z or 2, **machine)
    n_reel, vf_reel = essai.get('n') or 0.0, essai.get('vf') or 0.0
    comp = dict(n_theorie=theorie['rec_n'], fz_theorie=theorie['rec_fz'],
                vf_theorie=theorie['vf'] if z else None,
                rapport_n=None, rapport_vf=None,
                fz_reel=None, rapport_copeau=None)
    if n_reel:
        comp['rapport_n'] = n_reel / comp['n_theorie']
    if z and vf_reel:
        comp['rapport_vf'] = vf_reel / comp['vf_theorie']
        if n_reel:
            comp['fz_reel'] = vf_reel / (n_reel * z)
            comp['rapport_copeau'] = comp['fz_reel'] / comp['fz_theorie']
    return comp


def _plat(texte):
    """Minuscules, sans accents : ce qu'on tape à l'établi, gants aux mains."""
    decompose = unicodedata.normalize('NFD', str(texte))
    return ''.join(c for c in decompose
                   if not unicodedata.combining(c)).casefold()
