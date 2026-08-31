#!/usr/bin/env python3
# =========================================================================
# tests_carnet.py — le carnet retient-il, retrouve-t-il, protège-t-il ?
# © Atelier du Verdier — licence LGPL-2.1-or-later (cf. LICENSE).
# =========================================================================
# Tout se joue dans un dossier jetable : le vrai carnet — des verdicts
# d'établi — n'est jamais approché, et le dernier contrôle le vérifie.
# L'oracle du rapport de copeau vient du README : 21 000 tr/min à
# 800 mm/min en Ø6 deux dents, c'est 13 % du copeau utile.
#
#   python3 tests_carnet.py
# =========================================================================

import json
import sys
import tempfile
from pathlib import Path

import carnet_noyau as K

echecs = []


def verifier(titre, obtenu, attendu, tolerance=0.0):
    ok = (abs(obtenu - attendu) <= tolerance) if isinstance(attendu, (int, float)) \
        and not isinstance(attendu, bool) else (obtenu == attendu)
    print(('  OK   ' if ok else '  ÉCHEC') + '  ' + titre
          + ('' if ok else '  → obtenu %r, attendu %r' % (obtenu, attendu)))
    if not ok:
        echecs.append(titre)


def leve(fonction, *args, **kwargs):
    """Vrai si l'appel refuse (ValueError ou KeyError)."""
    try:
        fonction(*args, **kwargs)
        return False
    except (ValueError, KeyError):
        return True


defaut_existait = K.DOSSIER_DEFAUT.exists()
bac = Path(tempfile.mkdtemp(prefix='carnet-essais-'))

print("--- Un essai se normalise comme les saisies de l'appli ---")
e = K.nouvel_essai(matiere='bois-dur', essence='  Chêne de récup ', d='6,35',
                   z='2', n='21 000', vf='800', date='2026-08-30')
verifier("virgule décimale acceptée", e['d'], 6.35)
verifier("espace de groupement accepté", e['n'], 21000.0)
verifier("texte débarrassé de ses espaces", e['essence'], 'Chêne de récup')
verifier("champs non renseignés à zéro", (e['ap'], e['ae']), (0.0, 0.0))
verifier("le verdict peut attendre le résultat", e['verdict'], '')
verifier("sans diamètre : refusé", leve(K.nouvel_essai, matiere='bois-dur'), True)
verifier("matière étrangère au noyau : refusée",
         leve(K.nouvel_essai, matiere='granit', d='6'), True)
verifier("date hors ISO : refusée",
         leve(K.nouvel_essai, d='6', date='30/08/2026'), True)

print("\n--- Le carnet retient, relit, numérote ---")
verifier("pas encore de carnet : liste vide", K.charger(bac), [])
e1 = K.ajouter(K.nouvel_essai(matiere='bois-dur', essence='Chêne', d='6',
                              z='2', n='18000', vf='1500', operation='Rainure',
                              verdict='propre', date='2026-08-20'), dossier=bac)
e2 = K.ajouter(K.nouvel_essai(matiere='bois-dur', essence='Hêtre', d='8',
                              z='2', date='2026-08-25'), dossier=bac)
e3 = K.ajouter(K.nouvel_essai(matiere='mdf', d='6', travail='Porte hammam',
                              date='2026-08-30'), dossier=bac)
e4 = K.ajouter(K.nouvel_essai(matiere='bois-dur', essence='Chêne', d='6',
                              z='2', n='21000', vf='800', verdict='ça brûle',
                              date='2026-08-30'), dossier=bac)
verifier("l'identifiant porte la date", e1['id'], '2026-08-20-1')
verifier("deux essais le même jour se suivent",
         (e3['id'], e4['id']), ('2026-08-30-1', '2026-08-30-2'))
verifier("relecture : les quatre y sont", len(K.charger(bac)), 4)
verifier("relecture fidèle", K.charger(bac)[0], e1)
verifier("pas de fichier provisoire résiduel",
         (bac / (K.FICHIER_CARNET + '.tmp')).exists(), False)
verifier("champ inconnu à l'ajout : refusé",
         leve(K.ajouter, dict(d='6', verdit='typo'), dossier=bac), True)

print("\n--- La photo suit l'essai ---")
origine = bac / 'IMG_1234.JPG'
origine.write_bytes(b'pas vraiment un jpeg')
e4 = K.completer(e4['id'], photo=origine, dossier=bac)
verifier("nommée comme l'essai, extension en minuscules",
         e4['photo'], '2026-08-30-2.jpg')
verifier("copiée dans le carnet", K.chemin_photo(e4, bac).is_file(), True)
verifier("l'original n'a pas bougé", origine.is_file(), True)
autre = bac / 'reprise.png'
autre.write_bytes(b'pas vraiment un png')
e4 = K.completer(e4['id'], photo=autre, dossier=bac)
verifier("reprendre la photo remplace l'ancienne",
         e4['photo'], '2026-08-30-2.png')
verifier("l'ancienne ne traîne pas",
         (bac / K.SOUS_DOSSIER_PHOTOS / '2026-08-30-2.jpg').exists(), False)
verifier("photo introuvable : refusée",
         leve(K.completer, e4['id'], photo=bac / 'nulle-part.jpg', dossier=bac), True)
verifier("un essai sans photo n'a pas de chemin", K.chemin_photo(e1, bac), None)

print("\n--- Compléter après coup, sans rien perdre ---")
e2 = K.completer(e2['id'], verdict='sortie qui peluche', n='16 000', dossier=bac)
verifier("le verdict est arrivé", e2['verdict'], 'sortie qui peluche')
verifier("la broche corrigée est normalisée", e2['n'], 16000.0)
verifier("l'identifiant n'a pas bougé", e2['id'], '2026-08-25-1')
verifier("l'essence est restée", K.charger(bac)[1]['essence'], 'Hêtre')
verifier("essai inconnu : refusé",
         leve(K.completer, '1999-01-01-1', verdict='?', dossier=bac), True)
verifier("champ inconnu : refusé",
         leve(K.completer, e2['id'], vitesse='800', dossier=bac), True)

print("\n--- La consultation, avant chaque nouveau travail ---")
tous = K.charger(bac)
r = K.chercher(tous, matiere='bois-dur')
verifier("filtre matière : trois essais", len(r), 3)
verifier("le plus récent d'abord",
         [e['id'] for e in r], [e4['id'], e2['id'], e1['id']])
r = K.chercher(tous, matiere='bois-dur', d='6')
verifier("Ø le plus proche d'abord, le récent devant à Ø égal",
         [e['id'] for e in r], [e4['id'], e1['id'], e2['id']])
r = K.chercher(tous, texte='chene')
verifier("« chene » trouve le chêne", [e['id'] for e in r], [e4['id'], e1['id']])
verifier("le texte fouille aussi les verdicts",
         [e['id'] for e in K.chercher(tous, texte='BRULE')], [e4['id']])
verifier("le texte fouille aussi le travail",
         [e['id'] for e in K.chercher(tous, texte='hammam')], [e3['id']])
verifier("rien trouvé : liste vide", K.chercher(tous, texte='granit'), [])

print("\n--- Face à la théorie : le cas des 13 % du README ---")
temoin = K.nouvel_essai(matiere='bois-tendre', essence='Sapin', d='6', z='2',
                        n='21000', vf='800', date='2026-08-30')
comp = K.comparer_theorie(temoin)
verifier("broche conseillée retrouvée", comp['n_theorie'], 21000)
verifier("broche réelle au conseillé", comp['rapport_n'], 1.0, 1e-9)
verifier("copeau réel = 0,019 mm/dent", comp['fz_reel'], 0.019, 0.0005)
verifier("13 % du copeau utile : la fraise frotte",
         round(comp['rapport_copeau'] * 100), 13)
comp = K.comparer_theorie(K.charger(bac)[2])          # mdf, sans Z ni vitesses
verifier("sans dents : pas d'avance théorique", comp['vf_theorie'], None)
verifier("la broche conseillée, elle, reste", comp['n_theorie'] > 0, True)
verifier("sans matière : pas de comparaison",
         K.comparer_theorie(dict(matiere='', d=6.0)), None)

print("\n--- Supprimer retire tout ---")
K.supprimer(e3['id'], dossier=bac)
verifier("l'essai est sorti du carnet",
         [e['id'] for e in K.charger(bac)], [e1['id'], e2['id'], e4['id']])
K.supprimer(e4['id'], dossier=bac)
verifier("sa photo est partie avec lui",
         (bac / K.SOUS_DOSSIER_PHOTOS / '2026-08-30-2.png').exists(), False)
verifier("essai inconnu : refusé", leve(K.supprimer, e4['id'], dossier=bac), True)

print("\n--- Un carnet abîmé n'est JAMAIS écrasé ---")
fichier = bac / K.FICHIER_CARNET
sauvegarde = fichier.read_text(encoding='utf-8')
fichier.write_text('{ pas du json', encoding='utf-8')
verifier("charger lève", leve(K.charger, bac), True)
verifier("ajouter lève aussi",
         leve(K.ajouter, K.nouvel_essai(d='6'), dossier=bac), True)
verifier("et le fichier n'a pas été touché",
         fichier.read_text(encoding='utf-8'), '{ pas du json')
fichier.write_text(json.dumps({'pas': 'une liste'}), encoding='utf-8')
verifier("un carnet qui n'est pas une liste lève", leve(K.charger, bac), True)
fichier.write_text(sauvegarde, encoding='utf-8')
verifier("carnet réparé : tout revient", len(K.charger(bac)), 2)

verifier("le vrai carnet n'a jamais été approché",
         K.DOSSIER_DEFAUT.exists(), defaut_existait)

print()
if echecs:
    print("%d test(s) en échec : %s" % (len(echecs), ', '.join(echecs)))
    sys.exit(1)
print("Tout passe.")
