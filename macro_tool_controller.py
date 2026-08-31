# -*- coding: utf-8 -*-
# =========================================================================
# macro_tool_controller.py — remplir un Tool Controller depuis l'appli
# © Atelier du Verdier — licence LGPL-2.1-or-later (cf. LICENSE).
# =========================================================================
# Un fichier d'outil FreeCAD (.fctb) décrit la FRAISE — diamètre, dents,
# longueurs — et rien d'autre. Il ne peut pas porter de vitesses : celles-ci
# appartiennent au Tool Controller du Job, qui naît donc à zéro. C'est ce
# que cette macro épargne : elle lit la bibliothèque exportée par l'appli
# « Vitesses de coupe » et pose les cinq valeurs sur le contrôleur choisi.
#
# UTILISATION, dans FreeCAD :
#   1. ouvrir le document, avoir un Job avec au moins un Tool Controller ;
#   2. Macro → Macros… → macro_tool_controller.py → Exécuter ;
#   3. choisir le fichier JSON exporté par l'appli, puis l'outil, puis le
#      contrôleur à remplir.
#
# À INSTALLER une fois pour toutes en la copiant dans le dossier des macros
# (FreeCAD 1.1 : ~/.local/share/FreeCAD/v1-1/Macro — le dossier est VERSIONNÉ, un ~/.local/share/FreeCAD/Macro sans version peut exister et n'est PAS lu).
#
# =========================================================================
#  LE PIÈGE, ET IL EST SÉVÈRE
# =========================================================================
# Les propriétés HorizFeed, VertFeed, HorizRapid et VertRapid sont de type
# `App::PropertySpeed`, dont l'unité INTERNE est le mm/s — alors que
# l'interface, elle, affiche des mm/min. Écrire
#
#       tc.HorizFeed = 6300            #  ->  6 300 mm/s = 378 000 mm/min
#
# ne lève aucune erreur et donne une valeur SOIXANTE FOIS trop grande.
# Mesuré sur FreeCAD 1.1.3 le 31/08/2026. La seule écriture juste passe par
# une chaîne portant son unité :
#
#       tc.HorizFeed = "6300 mm/min"   #  ->  105 mm/s = 6 300 mm/min
#
# `FreeCAD.Units.Quantity(6300, FreeCAD.Units.Velocity)` tombe dans le même
# piège que le nombre nu. D'où `_poser_vitesse()` plus bas, qui est le seul
# endroit de cette macro où une vitesse est écrite.
# =========================================================================

import json
import os

import FreeCAD
import FreeCADGui
from PySide import QtGui

TITRE = "Vitesses de coupe → Tool Controller"


def _dire(texte, erreur=False):
    boite = QtGui.QMessageBox.critical if erreur else QtGui.QMessageBox.information
    boite(FreeCADGui.getMainWindow(), TITRE, texte)


def _poser_vitesse(tc, nom, valeur_mm_min):
    """Écrit une vitesse EN mm/min sur une propriété qui compte en mm/s.

    Le seul endroit de la macro où une vitesse est posée — pour qu'il n'y
    ait qu'un seul endroit où se tromper. Voir l'avertissement en tête.
    """
    if valeur_mm_min is None:
        return None
    try:
        v = float(valeur_mm_min)
    except (TypeError, ValueError):
        return None
    if v <= 0:
        return None
    setattr(tc, nom, "%f mm/min" % v)
    return getattr(tc, nom).getValueAs('mm/min')


def _controleurs_du_document(doc):
    """Tous les Tool Controllers du document, Job par Job."""
    trouves = []
    for obj in doc.Objects:
        # Un Tool Controller se reconnaît à ses propriétés, pas à son nom :
        # celui-ci est libre et souvent renommé.
        props = getattr(obj, 'PropertiesList', [])
        if 'HorizFeed' in props and 'SpindleSpeed' in props:
            trouves.append(obj)
    return trouves


def _choisir(titre, question, choix):
    """Une liste déroulante. Rend l'indice choisi, ou None si annulé."""
    valeur, ok = QtGui.QInputDialog.getItem(
        FreeCADGui.getMainWindow(), titre, question, choix, 0, False)
    if not ok:
        return None
    return choix.index(valeur)


def main():
    doc = FreeCAD.ActiveDocument
    if doc is None:
        _dire("Aucun document ouvert.", erreur=True)
        return

    controleurs = _controleurs_du_document(doc)
    if not controleurs:
        _dire("Ce document ne contient aucun Tool Controller.\n\n"
              "Créer d'abord un Job (atelier CAM), qui en contient un.",
              erreur=True)
        return

    # --- 1. Le fichier exporté par l'appli --------------------------------
    depart = os.path.expanduser('~')
    for essai in (os.path.join(depart, 'Téléchargements'),
                  os.path.join(depart, 'Downloads')):
        if os.path.isdir(essai):
            depart = essai
            break
    chemin, _ = QtGui.QFileDialog.getOpenFileName(
        FreeCADGui.getMainWindow(),
        "Bibliothèque exportée par « Vitesses de coupe »",
        os.path.join(depart, 'outils-vitesses-coupe.json'),
        "Bibliothèque d'outils (*.json)")
    if not chemin:
        return

    try:
        with open(chemin, 'r', encoding='utf-8') as f:
            donnees = json.load(f)
    except (OSError, ValueError) as e:
        _dire("Fichier illisible :\n%s" % e, erreur=True)
        return

    # L'appli exporte une LISTE d'outils. On accepte aussi un objet unique,
    # au cas où quelqu'un aurait copié un seul outil à la main.
    outils = donnees if isinstance(donnees, list) else [donnees]
    outils = [o for o in outils if isinstance(o, dict) and o.get('n')]
    if not outils:
        _dire("Aucun outil exploitable dans ce fichier.\n\n"
              "Attendu : la bibliothèque exportée par l'appli, avec au moins "
              "un outil portant sa vitesse de broche.", erreur=True)
        return

    # --- 2. Quel outil ----------------------------------------------------
    etiquettes = []
    for o in outils:
        etiquettes.append("%s  —  %s tr/min, %s mm/min"
                          % (o.get('name', 'sans nom'), o.get('n', '?'),
                             o.get('vf', '?')))
    i = _choisir(TITRE, "Quel outil ?", etiquettes)
    if i is None:
        return
    outil = outils[i]

    # --- 3. Quel contrôleur -----------------------------------------------
    noms = ["%s  (outil n° %s)" % (tc.Label, getattr(tc, 'ToolNumber', '?'))
            for tc in controleurs]
    j = _choisir(TITRE, "Quel Tool Controller remplir ?", noms)
    if j is None:
        return
    tc = controleurs[j]

    # --- 4. Poser les valeurs ---------------------------------------------
    doc.openTransaction("Vitesses de coupe → " + tc.Label)
    pose = {}
    try:
        broche = float(outil.get('n') or 0)
        if broche > 0:
            tc.SpindleSpeed = broche          # Float, pas une vitesse : pas d'unité
            pose['SpindleSpeed'] = "%.0f tr/min" % broche
        for propriete, cle in (('HorizFeed', 'vf'), ('VertFeed', 'plunge'),
                               ('HorizRapid', 'rapidH'), ('VertRapid', 'rapidV')):
            obtenu = _poser_vitesse(tc, propriete, outil.get(cle))
            if obtenu is not None:
                pose[propriete] = "%.0f mm/min" % obtenu
        doc.commitTransaction()
    except Exception as e:                    # noqa: BLE001 — on rend la main propre
        doc.abortTransaction()
        _dire("Rien n'a été modifié : %s" % e, erreur=True)
        return

    doc.recompute()

    manquants = [p for p in ('HorizFeed', 'VertFeed', 'HorizRapid', 'VertRapid')
                 if p not in pose]
    texte = ["%s reçoit les réglages de « %s » :"
             % (tc.Label, outil.get('name', 'sans nom')), ""]
    for cle in ('SpindleSpeed', 'HorizFeed', 'VertFeed', 'HorizRapid', 'VertRapid'):
        if cle in pose:
            texte.append("  %-13s %s" % (cle, pose[cle]))
    if manquants:
        texte += ["", "Non renseignés (absents du fichier, laissés tels quels) :",
                  "  " + ", ".join(manquants)]
    _dire("\n".join(texte))


main()
