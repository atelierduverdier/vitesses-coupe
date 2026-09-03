#!/usr/bin/env python3
# =========================================================================
# tests_interface.py — l'interface Qt fait-elle ce que le noyau calcule ?
# © Atelier du Verdier — licence LGPL-2.1-or-later (cf. LICENSE).
# =========================================================================
# Le noyau était juste et ses tests passaient ; l'appli, elle, ne suivait
# plus le diamètre : elle posait le conseillé dans le champ puis le relisait
# comme une saisie (défaut vu le 03/09/2026). Seul un test qui MANIPULE les
# widgets pouvait l'attraper — c'est celui-ci. Il tourne sans écran
# (QT_QPA_PLATFORM=offscreen) et sur une configuration JETABLE : les trois
# fichiers que l'appli écrit (réglages, vitesses FreeCAD, carnet) sont
# repointés vers un dossier temporaire avant la première fenêtre, et le
# dernier contrôle vérifie par leurs empreintes que les vrais n'ont pas bougé.
#
#   python3 tests_interface.py
# =========================================================================

import hashlib
import json
import os
import sys
import tempfile
from pathlib import Path

os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')

try:
    from PySide6.QtWidgets import QApplication
except ImportError:
    print("PySide6 absent : tests d'interface ignorés.")
    sys.exit(0)

import coupe_noyau as C
import carnet_noyau as K
import freecad_biblio as FB
import vitesses_coupe as V

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


def taper(champ, texte):
    """Ce que fait un utilisateur : le texte change ET `textEdited` part."""
    champ.edit.setText(texte)
    champ.edit.textEdited.emit(texte)


def vf_carte(f):
    return C.fmt(f.dernier['vf'])


# --- Le bac à sable, AVANT la première fenêtre ---------------------------
vrais = [V.FICHIER_CONF, FB.FICHIER_VITESSES, K.DOSSIER_DEFAUT / K.FICHIER_CARNET]
empreintes = [empreinte(p) for p in vrais]
bac = Path(tempfile.mkdtemp(prefix='vitesses-coupe-ui-'))
V.DOSSIER_CONF = bac / 'conf'
V.FICHIER_CONF = bac / 'conf' / 'reglages.json'
FB.DOSSIER_CONF = bac / 'conf'
FB.FICHIER_VITESSES = bac / 'conf' / 'vitesses-freecad.json'
K.DOSSIER_DEFAUT = bac / 'carnet'

app = QApplication.instance() or QApplication([])
f = V.Fenetre()

print("--- Au démarrage : le cas de la capture bureau.png ---")
verifier("broche affichée", f.f_n.valeur(), '21000')
verifier("copeau affiché", f.f_fz.valeur(), '0,15')
verifier("avance affichée", f.f_vf.valeur(), C.fmt(6300))
verifier("rien n'est encore SAISI", (f.f_n.saisi, f.f_fz.saisi, f.f_vf.saisi), ('', '', ''))

print("\n--- Changer le diamètre change le résultat (le défaut du 03/09) ---")
taper(f.f_d, '3')
verifier("Ø3 : la broche suit le conseillé", f.f_n.valeur(), '24000')
verifier("Ø3 : le copeau suit", f.f_fz.valeur(), '0,075')
verifier("Ø3 : la carte Vf = 24 000 × 2 × 0,075", vf_carte(f), C.fmt(3600))
taper(f.f_z, '1')
verifier("Z1 : l'avance est divisée par deux", vf_carte(f), C.fmt(1800))
taper(f.f_z, '2')

print("\n--- Une saisie, elle, est respectée — jusqu'au ↻ ---")
taper(f.f_n, '18000')
verifier("broche tapée : le calcul la prend", vf_carte(f), C.fmt(18000 * 2 * 0.075))
taper(f.f_d, '6')
verifier("changer Ø ne touche pas à la broche tapée", f.f_n.valeur(), '18000')
verifier("mais le copeau, non saisi, suit", f.f_fz.valeur(), '0,15')
f.btn_reset_n.click()
verifier("↻ : retour au conseillé", f.f_n.valeur(), '21000')
verifier("↻ : et la saisie est oubliée", f.f_n.saisi, '')

print("\n--- Changer de matière ou de sens repart des conseillés ---")
taper(f.f_n, '18000')
f.choisir_matiere('acier')
verifier("acier : la broche tapée pour le bois est oubliée", f.f_n.saisi, '')
verifier("acier Ø6 : broche conseillée 5 000", f.f_n.valeur(), '5000')
f.choisir_matiere('bois-tendre')

print("\n--- Mode broche et copeau avec une largeur ae : champ et carte d'accord ---")
taper(f.f_ae, '0,5')
f.choisir_mode('broche')
verifier("le champ Vf montre ce que le noyau a pris (amincissement compris)",
         C.num(f.f_vf.valeur(), 0), f.dernier['vf'], 1)
avant = vf_carte(f)
taper(f.f_z, '2')
verifier("une frappe quelconque ne fait pas sauter la carte", vf_carte(f), avant)
f.choisir_mode('copeau')
verifier("mode copeau : champ Vf = carte", C.num(f.f_vf.valeur(), 0), f.dernier['vf'], 1)
verifier("mode copeau : le copeau déduit vaut le conseillé (100 %)",
         '100 %' in f.f_fz.aide.text(), True)
taper(f.f_z, '2')
verifier("et il y reste après une frappe", '100 %' in f.f_fz.aide.text(), True)
taper(f.f_ae, '')
f.choisir_mode('avance')

print("\n--- Le sens inverse au clavier : je veux avancer à 800 ---")
f.choisir_mode('broche')
taper(f.f_vf, '800')
verifier("broche déduite 2 667", f.f_n.valeur(), C.fmt(2667))
verifier("le champ déduit est en lecture seule", f.f_n.edit.isReadOnly(), True)
f.f_n.edit.setFocus()
taper(f.f_vf, '1600')
verifier("le curseur dans le champ déduit ne fige pas son affichage",
         f.f_n.valeur(), C.fmt(5333))
f.f_vf.edit.setFocus()
f.choisir_mode('avance')

print("\n--- La bibliothèque de l'appli ---")
taper(f.f_d, '3.175')
f.e_nom.setText('Essai Ø3,17')
o = f.enregistrer_outil()
verifier("l'outil garde la saisie brute du Ø", o['d'], '3.175')
# Ø3,175 bois tendre : 40 000 tr/min plafonnés à 24 000, fz 0,025 × 3,175 = 0,079.
verifier("et les vitesses calculées : 24 000 × 2 × 0,079", (o['n'], o['vf']), ('24000', 3792))
taper(f.f_d, '6')
f.liste.setCurrentRow(0)
f._charger_selection()
verifier("recharger l'outil ramène son Ø", f.f_d.valeur(), '3.175')
verifier("sa broche est une SAISIE (elle ne bougera pas avec Ø)", f.f_n.saisi, '24000')
verifier("la carte retrouve son avance", vf_carte(f), C.fmt(3792))
f.choisir_matiere('bois-tendre')
taper(f.f_d, '6')

print("\n--- Le plafond : la broche proposée tient dessous ---")
taper(f.f_vfmax, '1500')
taper(f.f_fz, '0,13')
verifier("« Viser 5 500 » et non 6 000",
         'Viser 5 500' in f.o_avert.text(), True)
taper(f.f_vfmax, '99999')
f.btn_reset_fz.click()

print("\n--- Le carnet s'ouvre sur ce qu'on s'apprête à fraiser ---")
f.ouvrir_carnet()
cu = f.fen_carnet
verifier("pas d'erreur de lecture", cu.erreur, None)
verifier("préfiltré sur la matière", cu.combo_matiere.currentData(), 'bois-tendre')
verifier("et sur le Ø", cu.champ_diametre.text(), '6')
K.ajouter(K.nouvel_essai(matiere='bois-tendre', d='6', z='2', n='21000',
                         vf='800', verdict='ça brûle'))
cu._charger()
verifier("un essai noté apparaît", cu.liste.count(), 1)
cu.liste.setCurrentRow(0)
verifier("le rapport de copeau du README : 13 %", cu.lbl_copeau.text(), '13 %')
(bac / 'carnet' / 'carnet.json').write_text('{ abîmé', encoding='utf-8')
cu._charger()
verifier("carnet abîmé : bandeau, pas de plantage", cu.bandeau_erreur.isHidden(), False)
verifier("et plus de bouton « Noter »", cu.btn_noter.isEnabled(), False)

print("\n--- Le thème et les réglages ---")
f.basculer_theme()
verifier("nuit", (f.theme, f.btn_theme.text()), ('nuit', '☀  jour'))
f._sauver_reglages()
regl = json.loads(V.FICHIER_CONF.read_text(encoding='utf-8'))
verifier("les réglages vont dans le bac, thème compris", regl['theme'], 'nuit')
verifier("la bibliothèque y est", [o['name'] for o in regl['bibliotheque']], ['Essai Ø3,17'])
f.close()

print()
verifier("les VRAIS fichiers de l'utilisateur n'ont pas bougé",
         [empreinte(p) for p in vrais], empreintes)

print()
if echecs:
    print("%d test(s) en échec : %s" % (len(echecs), ', '.join(echecs)))
    sys.exit(1)
print("Tout passe.")
