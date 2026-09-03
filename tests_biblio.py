#!/usr/bin/env python3
# =========================================================================
# tests_biblio.py — l'aller-retour avec les fichiers d'outils de FreeCAD
# © Atelier du Verdier — licence LGPL-2.1-or-later (cf. LICENSE).
# =========================================================================
# Tout se joue dans un dossier jetable, et le fichier des vitesses de
# l'appli est REPOINTÉ dessus avant le premier appel : la vraie
# configuration (~/.config/vitesses-coupe) n'est jamais approchée, et le
# dernier contrôle le vérifie par son empreinte.
#
# Les fixtures reprennent ce que FreeCAD 1.1.3 écrit VRAIMENT — relevé le
# 31/08/2026 dans `2mm_Fishtail.fctb` après un aller-retour par le
# Gestionnaire : décimales à la VIRGULE (« 2,00 mm », locale française),
# `attribute` vidé, et ce qu'on y avait mis renvoyé dans `parameter`.
#
#   python3 tests_biblio.py
# =========================================================================

import hashlib
import json
import sys
import tempfile
from pathlib import Path

import freecad_biblio as FB
import coupe_noyau as C

echecs = []


def verifier(titre, obtenu, attendu, tolerance=0.0):
    ok = (abs(obtenu - attendu) <= tolerance) if isinstance(attendu, (int, float)) \
        and not isinstance(attendu, bool) else (obtenu == attendu)
    print(('  OK   ' if ok else '  ÉCHEC') + '  ' + titre
          + ('' if ok else '  → obtenu %r, attendu %r' % (obtenu, attendu)))
    if not ok:
        echecs.append(titre)


def empreinte(chemin):
    return hashlib.md5(chemin.read_bytes()).hexdigest() if chemin.exists() else None


# --- Le bac à sable, AVANT tout appel ------------------------------------
vrai_fichier = FB.FICHIER_VITESSES
empreinte_avant = empreinte(vrai_fichier)
bac = Path(tempfile.mkdtemp(prefix='biblio-freecad-'))
FB.DOSSIER_CONF = bac / 'conf'
FB.FICHIER_VITESSES = bac / 'conf' / 'vitesses-freecad.json'
outils = bac / 'CamAssets' / 'Tools'
(outils / 'Bit').mkdir(parents=True)
(outils / 'Library').mkdir(parents=True)

print("--- Lire ce que FreeCAD écrit, virgules comprises ---")
verifier("« 6.35 mm » -> 6,35", FB._nombre('6.35 mm'), 6.35)
verifier("« 2,00 mm » (locale française) -> 2", FB._nombre('2,00 mm'), 2.0)
verifier("un entier nu passe", FB._nombre(2), 2.0)
verifier("rien -> défaut", FB._nombre(None, 6), 6.0)
# Un outil tel que FreeCAD 1.1.3 l'a réécrit après un aller-retour.
(outils / 'Bit' / '2mm_Fishtail.fctb').write_text(json.dumps({
    "attribute": {}, "id": "2mm_Fishtail", "name": "2mm - Fishtail",
    "parameter": {"Chipload": "0,04 mm", "CuttingEdgeHeight": "12,00 mm",
                  "Diameter": "2,00 mm", "Flutes": 2, "Length": "38,00 mm",
                  "Material": "Carbide", "ShankDiameter": "3,17 mm",
                  "SpindleDirection": "Forward", "helice": "montante",
                  "plongeant": "True"},
    "shape": "endmill.fcstd", "shape-type": "Endmill", "version": 2}), encoding='utf-8')
o = FB.lire_outil(outils / 'Bit' / '2mm_Fishtail.fctb')
verifier("diamètre lu malgré la virgule", o['d'], 2.0)
verifier("dents", o['z'], 2)
verifier("copeau", o['fz'], 0.04)
verifier("forme ramenée au vocabulaire de l'appli", o['forme'], 'plat')
verifier("queue", o['queue'], 3.17)
# Un outil d'origine FreeCAD, sans Flutes ni Chipload.
(outils / 'Bit' / '5mm_Endmill.fctb').write_text(json.dumps({
    "attribute": {}, "name": "5mm Endmill",
    "parameter": {"CuttingEdgeHeight": "30.0000 mm", "Diameter": "5.0000 mm",
                  "Length": "50.0000 mm", "ShankDiameter": "3.0000 mm",
                  "Units": "Metric"},
    "shape": "endmill.fcstd", "shape-type": "Endmill", "version": 2}), encoding='utf-8')
o = FB.lire_outil(outils / 'Bit' / '5mm_Endmill.fctb')
verifier("sans Flutes : 2 dents par défaut", o['z'], 2)
verifier("sans Chipload : rien, l'appli calculera", o['fz'], None)
(outils / 'Bit' / '90degree_Vbit.fctb').write_text(json.dumps({
    "name": "90° V", "parameter": {"Diameter": "6 mm", "CuttingEdgeAngle": "90 °"},
    "shape": "v-bit.fcstd", "shape-type": "V-bit", "version": 2}), encoding='utf-8')
o = FB.lire_outil(outils / 'Bit' / '90degree_Vbit.fctb')
verifier("forme en V reconnue, angle repris", (o['forme'], o['extra']), ('vbit', 90.0))

print("\n--- Les bibliothèques ---")
(outils / 'Library' / 'Default.fctl').write_text(json.dumps({
    "label": "Default", "version": 1,
    "tools": [{"nr": 1, "path": "5mm_Endmill.fctb"},
              {"nr": 2, "path": "2mm_Fishtail.fctb"},
              {"nr": 3, "path": "disparu.fctb"}]}), encoding='utf-8')
libs = FB.bibliotheques(outils)
verifier("une bibliothèque trouvée", [b['label'] for b in libs], ['Default'])
lus = FB.outils_de(outils, libs[0])
verifier("un fichier disparu est passé sous silence", len(lus), 2)
verifier("le numéro d'outil suit", [o['nr'] for o in lus], [1, 2])

print("\n--- Écrire sans écraser ---")
verifier("nom de fichier sûr", FB._nom_de_fichier('Bois dur · Ø6,35'), 'Bois_dur_6_35.fctb')
g = C.geometrie('6.35', hauteur_coupe='22')
f1 = C.fichier_outil('Essai · Ø6,35', g, 2, 0.15)
nom1 = FB.ecrire_outil(outils, f1, libs[0], vitesses={'n': 21000, 'vf': 6300})
verifier("écrit sous le nom attendu", nom1, 'Essai_6_35.fctb')
verifier("inscrit dans la bibliothèque, numéro suivant",
         json.loads((outils / 'Library' / 'Default.fctl').read_text())['tools'][-1],
         {'nr': 4, 'path': 'Essai_6_35.fctb'})
verifier("les vitesses sont retenues À CÔTÉ, dans le bac",
         FB.vitesses_connues().get('Essai_6_35.fctb'), {'n': 21000, 'vf': 6300})
nom1bis = FB.ecrire_outil(outils, dict(f1), libs[0])
verifier("le même outil réécrit garde son fichier", nom1bis, nom1)
verifier("et ne s'inscrit pas deux fois",
         len(json.loads((outils / 'Library' / 'Default.fctl').read_text())['tools']), 4)
f2 = C.fichier_outil('Essai - Ø6.35', g, 2, 0.15)      # même nom de fichier, AUTRE outil
nom2 = FB.ecrire_outil(outils, f2, libs[0])
verifier("un autre outil au même nom de fichier est numéroté", nom2, 'Essai_6_35_2.fctb')
verifier("le premier n'a pas été écrasé",
         json.loads((outils / 'Bit' / nom1).read_text())['name'], 'Essai · Ø6,35')
f3 = C.fichier_outil('5mm Endmill', g, 2, 0.15)
verifier("l'outil d'origine de FreeCAD n'est réécrit que s'il porte le même nom",
         FB.ecrire_outil(outils, f3), '5mm_Endmill.fctb')
f4 = C.fichier_outil('5mm-Endmill', g, 2, 0.15)
verifier("un homonyme de fichier, pas d'outil, est numéroté",
         FB.ecrire_outil(outils, f4), '5mm_Endmill_2.fctb')

print("\n--- Une bibliothèque abîmée ne fait pas tomber l'écriture ---")
(outils / 'Library' / 'Nul.fctl').write_text(json.dumps({
    "label": "Nul", "version": 1,
    "tools": [{"nr": None, "path": "x.fctb"}, {"path": "y.fctb"}]}), encoding='utf-8')
lib_nulle = FB.bibliotheques(outils)[1]
nom = FB.ecrire_outil(outils, C.fichier_outil('Nouveau', g, 2, 0.1), lib_nulle)
verifier("nr absents ou nuls : on numérote quand même",
         json.loads((outils / 'Library' / 'Nul.fctl').read_text())['tools'][-1],
         {'nr': 1, 'path': nom})

print("\n--- Le magasin sans bibliothèque ---")
nom = FB.ecrire_outil(outils, C.fichier_outil('Seul', g, 1, 0.1), None)
verifier("écrit dans Bit sans toucher aux .fctl", (outils / 'Bit' / nom).is_file(), True)

verifier("la vraie configuration n'a jamais été approchée",
         empreinte(vrai_fichier), empreinte_avant)

print()
if echecs:
    print("%d test(s) en échec : %s" % (len(echecs), ', '.join(echecs)))
    sys.exit(1)
print("Tout passe.")
