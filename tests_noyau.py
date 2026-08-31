#!/usr/bin/env python3
# =========================================================================
# tests_noyau.py — le calcul rend-il les nombres attendus ?
# © Atelier du Verdier — licence LGPL-2.1-or-later (cf. LICENSE).
# =========================================================================
# Les valeurs de référence ne sont PAS recopiées de ce module : elles
# viennent des captures du dossier de remise (`screens/bureau.png`, qui
# affiche Vf 6 300, broche 21 000, Vz 2 205, Vc 396, 0,30 mm/tr) et du
# prototype fourni comme oracle. Un test qui reprend la formule qu'il
# vérifie ne vérifie rien.
#
#   python3 tests_noyau.py
# =========================================================================

import sys
import coupe_noyau as C

echecs = []


def verifier(titre, obtenu, attendu, tolerance=0.0):
    ok = (abs(obtenu - attendu) <= tolerance) if isinstance(attendu, (int, float)) \
        else (obtenu == attendu)
    print(('  OK   ' if ok else '  ÉCHEC') + '  ' + titre
          + ('' if ok else '  → obtenu %r, attendu %r' % (obtenu, attendu)))
    if not ok:
        echecs.append(titre)


print("--- Le cas de la capture bureau.png : bois tendre, Ø6, Z2 ---")
r = C.calculer('bois-tendre', '6', '2')
verifier("broche conseillée = 21 000 tr/min", r['n'], 21000)
verifier("avance = 6 300 mm/min", round(r['vf']), 6300)
verifier("plongée = 2 205 mm/min", round(r['vz']), 2205)
verifier("vitesse de coupe = 396 m/min", round(r['vc']), 396)
verifier("avance par tour = 0,30 mm/tr", round(r['fpr'], 2), 0.30)
verifier("copeau conseillé = 0,15 mm/dent", r['rec_fz'], 0.15)

print("\n--- Les trois sens de calcul se recoupent ---")
a = C.calculer('bois-tendre', '6', '2', mode='avance')
b = C.calculer('bois-tendre', '6', '2', mode='broche')
c = C.calculer('bois-tendre', '6', '2', mode='copeau')
verifier("avance identique en mode broche", round(b['vf']), round(a['vf']))
verifier("avance identique en mode copeau", round(c['vf']), round(a['vf']))
verifier("broche identique en mode broche", round(b['n']), round(a['n']))
verifier("copeau identique en mode copeau", round(c['fz'], 4), round(a['fz'], 4))

print("\n--- Le sens inverse : je veux avancer à 800 mm/min ---")
r = C.calculer('bois-tendre', '6', '2', mode='broche', vf='800')
verifier("broche déduite = 800 / (2 × 0,15) = 2 667 tr/min", round(r['n']), 2667)

print("\n--- Diagnostic : 21 000 tr/min à 800 mm/min, ça donne quoi ? ---")
r = C.calculer('bois-tendre', '6', '2', mode='copeau', vf='800', n='21000')
verifier("copeau réel = 800 / (21 000 × 2) = 0,019 mm/dent",
         round(r['fz'], 4), 0.019, tolerance=0.0005)

print("\n--- Amincissement du copeau en reprise de contour ---")
verifier("ae = D/2 : aucun amincissement", C.amincissement(6, 3), 1.0, 1e-9)
verifier("ae = 0,5 mm sur Ø6 : facteur 1,81", C.amincissement(6, 0.5), 1.809, 0.002)
verifier("ae = 0,1 mm sur Ø6 : facteur 3,906", C.amincissement(6, 0.1), 3.9057, 0.001)
verifier("ae vide : facteur 1", C.amincissement(6, 0), 1.0, 1e-9)
verifier("ae plus grand que la fraise : facteur 1", C.amincissement(6, 99), 1.0, 1e-9)
r = C.calculer('bois-tendre', '6', '2', ae='0.5')
verifier("l'avance est relevée d'autant", round(r['vf']), round(6300 * 1.809), 3)

print("\n--- Les entrées absurdes ne produisent pas d'absurdité ---")
for champ, valeur in [('d', '-6'), ('z', '-3'), ('fz', '-1'), ('vf', '-100')]:
    r = C.calculer('bois-tendre', **{champ: valeur})
    verifier("%s = %s : avance positive" % (champ, valeur), r['vf'] > 0, True)
r = C.calculer('bois-tendre', d='', z='')
verifier("champs vides : on retombe sur Ø6 Z2", (r['d'], r['z']), (6.0, 2))
r = C.calculer('bois-tendre', d='6,5')
verifier("virgule décimale acceptée", r['d'], 6.5)
r = C.calculer('bois-tendre', n='21 000')
verifier("espace de groupement accepté", r['n'], 21000.0)

print("\n--- Les avertissements ---")
r = C.calculer('bois-tendre', '6', '2', vf_max='1500')
verifier("plafond dépassé → un avertissement",
         any('plafond' in a for a in r['avertissements']), True)
r = C.calculer('bois-tendre', '6', '2', vf_max='99999')
verifier("plafond large → aucun avertissement de plafond",
         any('plafond' in a for a in r['avertissements']), False)
r = C.calculer('bois-tendre', '6', '2', ae='0.1', vf_max='99999')
verifier("passe très fine → avertissement d'amincissement",
         any('aminci' in a for a in r['avertissements']), True)
# La broche CONSEILLÉE est déjà bornée par le mini : pour tomber dessous il
# faut l'avoir saisie soi-même. Le handoff n'écrête pas cette saisie, il
# avertit — c'est à l'atelier de juger, pas à l'appli de décider.
r = C.calculer('bois-tendre', '6', '2', n='500', m_min='1000', vf_max='99999')
verifier("broche saisie sous le mini → avertissement",
         any('sous le mini' in a for a in r['avertissements']), True)
r = C.calculer('acier', '3', '2', m_min='8000', vf_max='99999')
verifier("la broche conseillée, elle, ne descend jamais sous le mini",
         r['n'] >= 8000, True)

print("\n--- La géométrie de la fraise ---")
g = C.geometrie(6)
verifier("rien de saisi : hauteur de coupe déduite à 3 × Ø", g['hauteur_coupe'], 18)
verifier("longueur déduite à 8 × Ø", g['longueur'], 48)
verifier("queue au diamètre de coupe", g['queue'], 6)
verifier("les trois sont signalées comme déduites", len(g['deduit']), 3)
g = C.geometrie(6, hauteur_coupe='22', longueur='60', queue='6.35')
verifier("valeurs saisies : hauteur respectée", g['hauteur_coupe'], 22)
verifier("queue en pouces acceptée", g['queue'], 6.35)
verifier("plus rien de déduit", len(g['deduit']), 0)
g = C.geometrie(6, longueur='10', hauteur_coupe='30')
verifier("longueur plus courte que la coupe : corrigée", g['longueur'] >= 30, True)
g = C.geometrie(6, forme='torique')
verifier("torique : un rayon de coin apparaît", 'rayon' in g, True)
g = C.geometrie(6, forme='vbit', angle='60')
verifier("V : l'angle est repris", g['angle'], 60)

print("\n--- Le fichier d'outil décrit la vraie fraise ---")
f = C.fichier_outil("Essai", C.geometrie(6, hauteur_coupe='22'), 2, 0.15)
verifier("forme plate", f['shape-type'], 'Endmill')
verifier("hauteur de coupe reprise", f['parameter']['CuttingEdgeHeight'], '22 mm')
verifier("nombre de dents", f['parameter']['Flutes'], 2)
f = C.fichier_outil("V", C.geometrie(6, forme='vbit', angle='90'), 1, 0.1)
verifier("forme en V", f['shape-type'], 'V-bit')
verifier("angle de pointe présent", 'CuttingEdgeAngle' in f['parameter'], True)
f = C.fichier_outil("T", C.geometrie(6, forme='torique', rayon='1.5'), 2, 0.15)
verifier("rayon de coin présent", f['parameter']['CornerRadius'], '1.5 mm')
verifier("l'hélice est conservée", f['attribute']['helice'], 'montante')

print("\n--- Les avertissements que la formule ne peut pas donner ---")
g = C.geometrie(6)
verifier("montante, plongeante : rien à signaler",
         len(C.avertissements_fraise(g, 'montante', True, '3–6 mm')), 0)
verifier("descendante : on prévient de l'évacuation",
         any('descendante' in a for a in C.avertissements_fraise(g, 'descendante', True, '3–6 mm')), True)
verifier("non plongeante : on impose la rampe",
         any('rampe' in a for a in C.avertissements_fraise(g, 'montante', False, '3–6 mm')), True)
g = C.geometrie(6, hauteur_coupe='4')
verifier("coupe plus courte que la passe conseillée : signalé",
         any('ne coupe que' in a for a in C.avertissements_fraise(g, 'montante', True, '3–6 mm')), True)

print("\n--- Les neuf matières répondent toutes ---")
for famille, items in C.MATIERES:
    for m in items:
        r = C.calculer(m['id'], '6', '2')
        ok = r['vf'] > 0 and r['n'] > 0 and r['fz'] > 0
        verifier("%s (%s)" % (m['label'], famille), ok, True)

print()
if echecs:
    print("%d test(s) en échec : %s" % (len(echecs), ', '.join(echecs)))
    sys.exit(1)
print("Tout passe.")
