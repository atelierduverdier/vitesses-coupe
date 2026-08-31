#!/usr/bin/env python3
# =========================================================================
# vitesses_coupe.py — l'appli de bureau, en PySide6
# © Atelier du Verdier — licence LGPL-2.1-or-later (cf. LICENSE).
# =========================================================================
# Même calcul que l'appli web du site (atelierduverdier.fr/coupe/) : les
# deux appellent `coupe_noyau`, qui porte les matières et les formules.
# Une seule source, donc pas de dérive possible entre les deux.
#
# La mise en page suit le même dossier de remise que l'appli web : deux
# colonnes, le résultat à droite qui reste visible pendant qu'on modifie
# les entrées, les matières groupées par famille, les réglages machine
# repliés. Thème JOUR par défaut, bascule jour/nuit en haut à droite.
#
#   python3 vitesses_coupe.py
# =========================================================================

import json
import sys
from pathlib import Path

from PySide6.QtCore import Qt, QTimer
from PySide6.QtGui import QAction, QFont, QFontDatabase, QGuiApplication, QKeySequence
from PySide6.QtWidgets import (
    QApplication, QButtonGroup, QCheckBox, QFileDialog, QFrame, QGridLayout,
    QHBoxLayout, QInputDialog, QLabel, QLineEdit, QListWidget, QListWidgetItem,
    QMainWindow, QMessageBox, QPushButton, QScrollArea, QSizePolicy,
    QVBoxLayout, QWidget)

sys.path.insert(0, str(Path(__file__).resolve().parent))
import coupe_noyau as C
import freecad_biblio as FB

APP_NOM = "Vitesses de coupe"
VERSION = "1.0.0"

# Les réglages et la bibliothèque vivent à côté des autres configurations
# de l'utilisateur, pas dans le dossier du programme : celui-ci peut être
# un dépôt git que l'on met à jour.
DOSSIER_CONF = Path.home() / '.config' / 'vitesses-coupe'
FICHIER_CONF = DOSSIER_CONF / 'reglages.json'


# =========================================================================
#  Les deux palettes — les mêmes jetons que l'appli web
# =========================================================================
JOUR = dict(
    page='#f5f4f1', card='#ffffff', result='#ffffff', field='#ffffff',
    calc='#fdf5ec', seg='#eceae5',
    field_bd='#d7d4cd', card_bd='#e4e1da',
    result_bd='#ecd6b6', result_bd_warn='#eebfae',
    txt='#1b1a17', txt_strong='#111110', btn_off='#403d37',
    label='#55524c', second='#6a675f', help='#7b776f', section='#84806f',
    placeholder='#a5a199',
    accent='#f0913a', accent_ink='#a95c08', on_accent='#17120c',
    warn_bar='#d9481f', warn_title='#a83a17', warn_txt='#6f2a12', warn_bg='#fdefe9',
)
NUIT = dict(
    page='#0a0a0b', card='#101012', result='#121114', field='#17171a',
    calc='#0d0d0f', seg='#131316',
    field_bd='#2c2c31', card_bd='#24242a',
    result_bd='#2b2118', result_bd_warn='#4a1f18',
    txt='#eae8e4', txt_strong='#f2f0ec', btn_off='#cfcdc8',
    label='#a9a7a2', second='#8b8985', help='#74736f', section='#6d6c68',
    placeholder='#5c5b57',
    accent='#f0913a', accent_ink='#f0913a', on_accent='#17120c',
    warn_bar='#ff6b4a', warn_title='#ff8a6b', warn_txt='#ffcbbc', warn_bg='#2a1310',
)


def police_mono():
    """Une police à chasse fixe qui existe vraiment sur cette machine.

    La maquette demande JetBrains Mono ; si elle n'est pas installée, Qt
    remplace SILENCIEUSEMENT par la police par défaut — et les colonnes de
    chiffres cessent d'être alignées sans que rien ne le dise. On cherche
    donc dans l'ordre, et on retombe sur la mono du système.
    """
    dispo = set(QFontDatabase.families())
    for nom in ('JetBrains Mono', 'DejaVu Sans Mono', 'Liberation Mono',
                'Noto Sans Mono', 'Monospace'):
        if nom in dispo:
            return nom
    return QFontDatabase.systemFont(QFontDatabase.FixedFont).family()


def police_texte():
    dispo = set(QFontDatabase.families())
    for nom in ('IBM Plex Sans', 'Inter', 'Noto Sans', 'DejaVu Sans', 'Cantarell'):
        if nom in dispo:
            return nom
    return QGuiApplication.font().family()


# =========================================================================
#  Petits composants
# =========================================================================
class Champ(QWidget):
    """Un libellé, un champ de saisie, une ligne d'aide dessous."""

    def __init__(self, libelle, unite='', place='', parent=None):
        super().__init__(parent)
        v = QVBoxLayout(self)
        v.setContentsMargins(0, 0, 0, 0)
        v.setSpacing(0)
        self.lbl = QLabel(libelle + (
            '  <span style="color:#8b8985">(%s)</span>' % unite if unite else ''))
        self.lbl.setTextFormat(Qt.RichText)
        self.lbl.setObjectName('labelChamp')
        self.edit = QLineEdit()
        self.edit.setPlaceholderText(place)
        self.edit.setMinimumHeight(52)
        self.aide = QLabel('')
        self.aide.setObjectName('aide')
        self.aide.setWordWrap(True)
        v.addWidget(self.lbl)
        v.addSpacing(7)
        v.addWidget(self.edit)
        v.addSpacing(6)
        v.addWidget(self.aide)

    def valeur(self):
        return self.edit.text()

    def poser(self, texte):
        """Écrit sans déclencher l'édition, et sans voler le curseur."""
        if self.edit.hasFocus():
            return
        b = self.edit.blockSignals(True)
        self.edit.setText(texte)
        self.edit.blockSignals(b)

    def marquer_calcule(self, calcule):
        self.edit.setReadOnly(calcule)
        self.edit.setProperty('calcule', 'oui' if calcule else 'non')
        self.edit.style().unpolish(self.edit)
        self.edit.style().polish(self.edit)


class Carte(QFrame):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName('carte')


def titre_section(texte):
    l = QLabel(texte.upper())
    l.setObjectName('sectTitre')
    return l


# =========================================================================
#  La fenêtre
# =========================================================================
class Fenetre(QMainWindow):

    def __init__(self):
        super().__init__()
        self.setWindowTitle(APP_NOM)
        self.theme = 'jour'
        self.mode = 'avance'
        self.mat = 'bois-tendre'
        self.forme = 'plat'
        self.helice = 'montante'
        self.bibliotheque = []
        self.dossier_fc = ''      # l'installation FreeCAD choisie
        self.fichier_fc = ''      # le .fctb d'où vient l'outil courant
        self.mono = police_mono()
        self.sans = police_texte()

        self._construire()
        self._charger_reglages()
        self._appliquer_theme()
        self.recalculer()
        self.resize(1180, 820)

    # ---------------------------------------------------------------- UI
    def _construire(self):
        central = QWidget()
        self.setCentralWidget(central)
        racine = QVBoxLayout(central)
        racine.setContentsMargins(20, 20, 20, 20)
        racine.setSpacing(0)

        # --- En-tête ---
        entete = QHBoxLayout()
        entete.setSpacing(12)
        bloc_titre = QVBoxLayout()
        bloc_titre.setSpacing(2)
        t = QLabel(APP_NOM)
        t.setObjectName('titre')
        st = QLabel("Fraise carbure — des points de départ, à affiner sur la machine.")
        st.setObjectName('sousTitre')
        bloc_titre.addWidget(t)
        bloc_titre.addWidget(st)
        entete.addLayout(bloc_titre)
        entete.addStretch(1)
        self.btn_theme = QPushButton('☾  nuit')
        self.btn_theme.setObjectName('btnTheme')
        self.btn_theme.setCursor(Qt.PointingHandCursor)
        self.btn_theme.clicked.connect(self.basculer_theme)
        entete.addWidget(self.btn_theme)
        racine.addLayout(entete)
        racine.addSpacing(20)

        # --- Deux colonnes ---
        colonnes = QHBoxLayout()
        colonnes.setSpacing(28)

        gauche_hote = QWidget()
        gauche = QVBoxLayout(gauche_hote)
        gauche.setContentsMargins(0, 0, 0, 0)
        gauche.setSpacing(26)

        gauche.addWidget(self._bloc_matieres())
        gauche.addWidget(self._bloc_outil())
        gauche.addWidget(self._bloc_fraise())
        gauche.addWidget(self._bloc_calcul())
        gauche.addWidget(self._bloc_largeur())
        gauche.addWidget(self._bloc_machine())
        gauche.addStretch(1)

        # La colonne de gauche défile ; le résultat, lui, ne bouge pas.
        defil = QScrollArea()
        defil.setWidgetResizable(True)
        defil.setFrameShape(QFrame.NoFrame)
        defil.setWidget(gauche_hote)
        defil.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        colonnes.addWidget(defil, 1)

        rail = QVBoxLayout()
        rail.setSpacing(16)
        rail.addWidget(self._bloc_resultat())
        rail.addWidget(self._bloc_biblio())
        rail.addStretch(1)
        hote_rail = QWidget()
        hote_rail.setLayout(rail)
        hote_rail.setFixedWidth(396)
        colonnes.addWidget(hote_rail, 0)

        racine.addLayout(colonnes, 1)

        # Raccourcis
        for seq, fn in ((QKeySequence('Ctrl+J'), self.basculer_theme),
                        (QKeySequence('Ctrl+S'), self.enregistrer_outil),
                        (QKeySequence('Ctrl+Q'), self.close)):
            a = QAction(self)
            a.setShortcut(seq)
            a.triggered.connect(fn)
            self.addAction(a)

    def _bloc_matieres(self):
        w = QWidget()
        v = QVBoxLayout(w)
        v.setContentsMargins(0, 0, 0, 0)
        v.setSpacing(8)
        v.addWidget(titre_section('Matière'))
        self.grp_mat = QButtonGroup(self)
        self.grp_mat.setExclusive(True)
        for famille, items in C.MATIERES:
            ligne = QHBoxLayout()
            ligne.setSpacing(12)
            lf = QLabel(famille)
            lf.setObjectName('famille')
            lf.setFixedWidth(62)
            lf.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
            ligne.addWidget(lf)
            grille = QHBoxLayout()
            grille.setSpacing(8)
            for m in items:
                b = QPushButton(m['label'])
                b.setCheckable(True)
                b.setObjectName('choix')
                b.setMinimumHeight(48)
                b.setCursor(Qt.PointingHandCursor)
                b.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
                b.setChecked(m['id'] == self.mat)
                b.clicked.connect(lambda _=False, mid=m['id']: self.choisir_matiere(mid))
                self.grp_mat.addButton(b)
                grille.addWidget(b)
            # Les familles courtes ne doivent pas étirer leurs boutons sur
            # toute la largeur : on complète avec du vide.
            for _ in range(4 - len(items)):
                grille.addStretch(1)
            ligne.addLayout(grille, 1)
            v.addLayout(ligne)
        return w

    def _bloc_outil(self):
        w = QWidget()
        v = QVBoxLayout(w)
        v.setContentsMargins(0, 0, 0, 0)
        v.setSpacing(0)
        v.addWidget(titre_section('Outil'))
        v.addSpacing(12)
        duo = QHBoxLayout()
        duo.setSpacing(16)
        self.f_d = Champ('Diamètre', 'mm')
        self.f_d.edit.setText('6')
        self.f_z = Champ('Nombre de dents', 'Z')
        self.f_z.edit.setText('2')
        for f in (self.f_d, self.f_z):
            f.edit.textEdited.connect(self.recalculer)
            duo.addWidget(f)
        v.addLayout(duo)
        return w

    def _bloc_fraise(self):
        """La géométrie de la fraise — repliée, car elle ne change aucun chiffre.

        Elle sert au fichier d'outil FreeCAD, qui décrirait sinon une fraise
        déduite du seul diamètre, et aux avertissements que la formule ne
        peut pas donner.
        """
        carte = Carte()
        v = QVBoxLayout(carte)
        v.setContentsMargins(18, 12, 18, 12)
        v.setSpacing(0)

        tete = QHBoxLayout()
        bloc = QVBoxLayout()
        bloc.setSpacing(4)
        bloc.addWidget(titre_section('La fraise en détail'))
        self.lbl_resume_fraise = QLabel('')
        self.lbl_resume_fraise.setObjectName('resume')
        bloc.addWidget(self.lbl_resume_fraise)
        tete.addLayout(bloc)
        tete.addStretch(1)
        self.btn_fraise = QPushButton('préciser')
        self.btn_fraise.setObjectName('bascule')
        self.btn_fraise.setCheckable(True)
        self.btn_fraise.setCursor(Qt.PointingHandCursor)
        self.btn_fraise.clicked.connect(self._basculer_fraise)
        tete.addWidget(self.btn_fraise, 0, Qt.AlignTop)
        v.addLayout(tete)

        self.corps_fraise = QWidget()
        vf = QVBoxLayout(self.corps_fraise)
        vf.setContentsMargins(0, 14, 0, 4)
        vf.setSpacing(14)
        note = QLabel("Rien de tout ceci ne change les vitesses. C'est ce qui part "
                      "dans le fichier d'outil FreeCAD.")
        note.setObjectName('aide')
        note.setWordWrap(True)
        vf.addWidget(note)

        # Forme du bout
        lf = QLabel('Forme du bout')
        lf.setObjectName('labelChamp')
        vf.addWidget(lf)
        ligne_f = QHBoxLayout()
        ligne_f.setSpacing(8)
        self.btn_formes = {}
        for f in C.FORMES:
            b = QPushButton(f['label'])
            b.setCheckable(True)
            b.setObjectName('choix')
            b.setMinimumHeight(44)
            b.setCursor(Qt.PointingHandCursor)
            b.setChecked(f['id'] == self.forme)
            b.clicked.connect(lambda _=False, i=f['id']: self.choisir_forme(i))
            self.btn_formes[f['id']] = b
            ligne_f.addWidget(b)
        vf.addLayout(ligne_f)

        g = QGridLayout()
        g.setHorizontalSpacing(14)
        g.setVerticalSpacing(14)
        self.f_hcoupe = Champ('Hauteur de coupe', 'mm', 'déduite')
        self.f_lgtot = Champ('Longueur totale', 'mm', 'déduite')
        self.f_queue = Champ('Diamètre de queue', 'mm', '= diamètre de coupe')
        self.f_extra = Champ('Rayon de coin', 'mm', 'déduit')
        g.addWidget(self.f_hcoupe, 0, 0)
        g.addWidget(self.f_lgtot, 0, 1)
        g.addWidget(self.f_queue, 1, 0)
        g.addWidget(self.f_extra, 1, 1)
        for f in (self.f_hcoupe, self.f_lgtot, self.f_queue, self.f_extra):
            f.edit.textEdited.connect(self.recalculer)
        vf.addLayout(g)

        # Sens de l'hélice
        lh = QLabel("Sens de l'hélice")
        lh.setObjectName('labelChamp')
        vf.addWidget(lh)
        ligne_h = QHBoxLayout()
        ligne_h.setSpacing(8)
        self.btn_helices = {}
        for h in C.HELICES:
            b = QPushButton(h['label'])
            b.setCheckable(True)
            b.setObjectName('choix')
            b.setMinimumHeight(44)
            b.setCursor(Qt.PointingHandCursor)
            b.setChecked(h['id'] == self.helice)
            b.clicked.connect(lambda _=False, i=h['id']: self.choisir_helice(i))
            self.btn_helices[h['id']] = b
            ligne_h.addWidget(b)
        vf.addLayout(ligne_h)
        self.lbl_note_helice = QLabel('')
        self.lbl_note_helice.setObjectName('aide')
        self.lbl_note_helice.setWordWrap(True)
        vf.addWidget(self.lbl_note_helice)

        self.case_plongeant = QCheckBox(
            "Bout plongeant (fishtail) — peut entrer droit dans la matière")
        self.case_plongeant.setChecked(True)
        self.case_plongeant.setCursor(Qt.PointingHandCursor)
        self.case_plongeant.stateChanged.connect(self.recalculer)
        vf.addWidget(self.case_plongeant)

        self.corps_fraise.hide()
        v.addWidget(self.corps_fraise)
        return carte

    def choisir_forme(self, fid):
        self.forme = fid
        self.f_extra.edit.clear()
        for i, b in self.btn_formes.items():
            b.setChecked(i == fid)
        self.recalculer()

    def choisir_helice(self, hid):
        self.helice = hid
        for i, b in self.btn_helices.items():
            b.setChecked(i == hid)
        self.recalculer()

    def _basculer_fraise(self):
        ouvert = self.btn_fraise.isChecked()
        self.corps_fraise.setVisible(ouvert)
        self.btn_fraise.setText('replier' if ouvert else 'préciser')

    def _bloc_calcul(self):
        w = QWidget()
        v = QVBoxLayout(w)
        v.setContentsMargins(0, 0, 0, 0)
        v.setSpacing(0)
        v.addWidget(titre_section("Ce que l'appli calcule"))
        v.addSpacing(12)

        seg = QHBoxLayout()
        seg.setSpacing(8)
        self.btn_modes = {}
        for cle, libelle in (('avance', "L'avance"), ('broche', 'La broche'),
                             ('copeau', 'Le copeau')):
            b = QPushButton(libelle)
            b.setCheckable(True)
            b.setObjectName('choix')
            b.setMinimumHeight(48)
            b.setCursor(Qt.PointingHandCursor)
            b.setChecked(cle == self.mode)
            b.clicked.connect(lambda _=False, c=cle: self.choisir_mode(c))
            self.btn_modes[cle] = b
            seg.addWidget(b)
        v.addLayout(seg)
        v.addSpacing(20)

        duo = QHBoxLayout()
        duo.setSpacing(16)
        # Broche, avec son bouton « revenir au conseillé »
        bloc_n = QVBoxLayout()
        bloc_n.setSpacing(0)
        self.f_n = Champ('Vitesse de broche', 'tr/min')
        ligne_n = QHBoxLayout()
        ligne_n.setSpacing(8)
        ligne_n.addWidget(self.f_n.edit)
        self.btn_reset_n = QPushButton('↻')
        self.btn_reset_n.setObjectName('reset')
        self.btn_reset_n.setFixedWidth(44)
        self.btn_reset_n.setMinimumHeight(52)
        self.btn_reset_n.setToolTip('Revenir au conseillé')
        self.btn_reset_n.setCursor(Qt.PointingHandCursor)
        self.btn_reset_n.clicked.connect(lambda: (self.f_n.edit.clear(), self.recalculer()))
        ligne_n.addWidget(self.btn_reset_n)
        bloc_n.addWidget(self.f_n.lbl)
        bloc_n.addSpacing(7)
        bloc_n.addLayout(ligne_n)
        bloc_n.addSpacing(6)
        bloc_n.addWidget(self.f_n.aide)

        bloc_fz = QVBoxLayout()
        bloc_fz.setSpacing(0)
        self.f_fz = Champ('Copeau par dent', 'fz, mm')
        ligne_fz = QHBoxLayout()
        ligne_fz.setSpacing(8)
        ligne_fz.addWidget(self.f_fz.edit)
        self.btn_reset_fz = QPushButton('↻')
        self.btn_reset_fz.setObjectName('reset')
        self.btn_reset_fz.setFixedWidth(44)
        self.btn_reset_fz.setMinimumHeight(52)
        self.btn_reset_fz.setToolTip('Revenir au conseillé')
        self.btn_reset_fz.setCursor(Qt.PointingHandCursor)
        self.btn_reset_fz.clicked.connect(lambda: (self.f_fz.edit.clear(), self.recalculer()))
        ligne_fz.addWidget(self.btn_reset_fz)
        bloc_fz.addWidget(self.f_fz.lbl)
        bloc_fz.addSpacing(7)
        bloc_fz.addLayout(ligne_fz)
        bloc_fz.addSpacing(6)
        bloc_fz.addWidget(self.f_fz.aide)

        duo.addLayout(bloc_n)
        duo.addLayout(bloc_fz)
        v.addLayout(duo)
        v.addSpacing(20)

        self.f_vf = Champ('Avance de travail', 'Vf, mm/min')
        v.addWidget(self.f_vf)
        for f in (self.f_n, self.f_fz, self.f_vf):
            f.edit.textEdited.connect(self.recalculer)
        return w

    def _bloc_largeur(self):
        w = QWidget()
        v = QVBoxLayout(w)
        v.setContentsMargins(0, 0, 0, 0)
        v.setSpacing(0)
        ligne = QHBoxLayout()
        ligne.setSpacing(8)
        lbl = QLabel('Largeur de coupe  <span style="color:#8b8985">(ae, mm)</span>')
        lbl.setTextFormat(Qt.RichText)
        lbl.setObjectName('labelChamp')
        ligne.addWidget(lbl)
        self.btn_aide_ae = QPushButton('?')
        self.btn_aide_ae.setObjectName('pastilleAide')
        self.btn_aide_ae.setFixedSize(22, 22)
        self.btn_aide_ae.setCheckable(True)
        self.btn_aide_ae.setCursor(Qt.PointingHandCursor)
        self.btn_aide_ae.clicked.connect(self._basculer_aide_ae)
        ligne.addWidget(self.btn_aide_ae)
        ligne.addStretch(1)
        v.addLayout(ligne)
        v.addSpacing(7)

        self.f_ae = Champ('', place='pleine largeur')
        self.f_ae.lbl.hide()
        self.f_ae.edit.textEdited.connect(self.recalculer)
        v.addWidget(self.f_ae)

        self.bloc_aide_ae = QLabel(
            "Ce que la fraise mord <b>sur le côté</b>, à plat — pas la profondeur "
            "(celle-là c'est Ap, rappelée dans le résultat).<br><br>"
            "<b>Rainure ou découpe traversante</b> : laisser vide.<br><br>"
            "<b>Reprise de contour</b> : mettre la surépaisseur qu'on rase, souvent "
            "0,1 à 0,5 mm. Le copeau devient bien plus fin que prévu et la fraise "
            "brûle au lieu de couper ; l'appli corrige l'avance en conséquence.")
        self.bloc_aide_ae.setObjectName('blocAide')
        self.bloc_aide_ae.setWordWrap(True)
        self.bloc_aide_ae.hide()
        v.addWidget(self.bloc_aide_ae)
        return w

    def _bloc_machine(self):
        carte = Carte()
        v = QVBoxLayout(carte)
        v.setContentsMargins(18, 12, 18, 12)
        v.setSpacing(0)

        tete = QHBoxLayout()
        bloc = QVBoxLayout()
        bloc.setSpacing(4)
        bloc.addWidget(titre_section('Machine'))
        self.lbl_resume = QLabel('')
        self.lbl_resume.setObjectName('resume')
        bloc.addWidget(self.lbl_resume)
        tete.addLayout(bloc)
        tete.addStretch(1)
        self.btn_machine = QPushButton('modifier')
        self.btn_machine.setObjectName('bascule')
        self.btn_machine.setCheckable(True)
        self.btn_machine.setCursor(Qt.PointingHandCursor)
        self.btn_machine.clicked.connect(self._basculer_machine)
        tete.addWidget(self.btn_machine, 0, Qt.AlignTop)
        v.addLayout(tete)

        self.corps_machine = QWidget()
        g = QGridLayout(self.corps_machine)
        g.setContentsMargins(0, 14, 0, 4)
        g.setHorizontalSpacing(14)
        g.setVerticalSpacing(14)
        sous = QLabel("Réglé une fois pour toutes, pas à chaque calcul.")
        sous.setObjectName('aide')
        g.addWidget(sous, 0, 0, 1, 2)
        self.f_min = Champ('Broche min', 'tr/min')
        self.f_min.edit.setText('1000')
        self.f_max = Champ('Broche max', 'tr/min')
        self.f_max.edit.setText('24000')
        self.f_plunge = Champ('Plongée', '% de Vf')
        self.f_plunge.edit.setText('35')
        self.f_vfmax = Champ('Avance max', 'mm/min')
        self.f_vfmax.edit.setText('1500')
        self.f_vfmax.aide.setText("Ce que la machine tient vraiment.")
        # Les rapides n'entrent PAS dans le calcul : ce sont des vitesses de
        # transport (G0), propres à la machine. Elles sont là parce que le
        # Tool Controller de FreeCAD les réclame, et qu'il vaut mieux les
        # emporter avec l'outil que les retaper de mémoire.
        self.f_rapidh = Champ('Rapide horizontal', 'mm/min')
        self.f_rapidh.edit.setText('8000')
        self.f_rapidv = Champ('Rapide vertical', 'mm/min')
        self.f_rapidv.edit.setText('2700')
        self.f_rapidv.aide.setText("Déplacements hors matière, lus dans la config machine.")
        g.addWidget(self.f_min, 1, 0)
        g.addWidget(self.f_max, 1, 1)
        g.addWidget(self.f_plunge, 2, 0)
        g.addWidget(self.f_vfmax, 2, 1)
        g.addWidget(self.f_rapidh, 3, 0)
        g.addWidget(self.f_rapidv, 3, 1)
        for f in (self.f_min, self.f_max, self.f_plunge, self.f_vfmax,
                  self.f_rapidh, self.f_rapidv):
            f.edit.textEdited.connect(self.recalculer)
        self.corps_machine.hide()
        v.addWidget(self.corps_machine)
        return carte

    def _bloc_resultat(self):
        self.carte_resultat = QFrame()
        self.carte_resultat.setObjectName('resultat')
        v = QVBoxLayout(self.carte_resultat)
        v.setContentsMargins(0, 0, 0, 0)
        v.setSpacing(0)

        chiffres = QWidget()
        g = QGridLayout(chiffres)
        g.setContentsMargins(20, 20, 20, 4)
        g.setHorizontalSpacing(16)
        g.setVerticalSpacing(22)

        def cellule(cle, grand):
            hote = QWidget()
            vv = QVBoxLayout(hote)
            vv.setContentsMargins(0, 0, 0, 0)
            vv.setSpacing(6)
            k = QLabel(cle.upper())
            k.setObjectName('sectTitre')
            val = QLabel('—')
            val.setObjectName('valGrande' if grand else 'valPetite')
            val.setMinimumHeight(38 if grand else 26)
            vv.addWidget(k)
            vv.addWidget(val)
            return hote, val

        h1, self.o_vf = cellule('Avance Vf', True)
        h2, self.o_n = cellule('Broche', True)
        h3, self.o_vz = cellule('Plongée Vz', False)
        h4, self.o_fpr = cellule('Avance/tour', False)
        g.addWidget(h1, 0, 0); g.addWidget(h2, 0, 1)
        g.addWidget(h3, 1, 0); g.addWidget(h4, 1, 1)
        v.addWidget(chiffres)

        ctx = QWidget()
        vc = QVBoxLayout(ctx)
        vc.setContentsMargins(20, 20, 20, 20)
        vc.setSpacing(8)
        self.o_contexte = QLabel('')
        self.o_contexte.setObjectName('contexte')
        self.o_contexte.setWordWrap(True)
        self.o_note = QLabel('')
        self.o_note.setObjectName('note')
        self.o_note.setWordWrap(True)
        vc.addWidget(self.o_contexte)
        vc.addWidget(self.o_note)
        v.addWidget(ctx)

        self.bloc_avert = QFrame()
        self.bloc_avert.setObjectName('avert')
        va = QHBoxLayout(self.bloc_avert)
        va.setContentsMargins(20, 16, 20, 16)
        va.setSpacing(12)
        barre = QFrame()
        barre.setObjectName('barreAvert')
        barre.setFixedWidth(6)
        va.addWidget(barre)
        bloc = QVBoxLayout()
        bloc.setSpacing(6)
        ta = QLabel('À CORRIGER')
        ta.setObjectName('titreAvert')
        self.o_avert = QLabel('')
        self.o_avert.setObjectName('texteAvert')
        self.o_avert.setWordWrap(True)
        bloc.addWidget(ta)
        bloc.addWidget(self.o_avert)
        va.addLayout(bloc, 1)
        self.bloc_avert.hide()
        v.addWidget(self.bloc_avert)
        return self.carte_resultat

    def _bloc_biblio(self):
        carte = Carte()
        v = QVBoxLayout(carte)
        v.setContentsMargins(16, 16, 16, 16)
        v.setSpacing(0)
        ligne = QHBoxLayout()
        ligne.setSpacing(10)
        self.e_nom = QLineEdit()
        self.e_nom.setPlaceholderText("Nom de l'outil")
        self.e_nom.setMinimumHeight(48)
        self.e_nom.returnPressed.connect(self.enregistrer_outil)
        b = QPushButton('Enregistrer')
        b.setObjectName('primaire')
        b.setMinimumHeight(48)
        b.setCursor(Qt.PointingHandCursor)
        b.clicked.connect(self.enregistrer_outil)
        ligne.addWidget(self.e_nom, 1)
        ligne.addWidget(b, 0)
        v.addLayout(ligne)

        self.lbl_biblio = QLabel('BIBLIOTHÈQUE (0)')
        self.lbl_biblio.setObjectName('sectTitre')
        v.addSpacing(18)
        v.addWidget(self.lbl_biblio)
        v.addSpacing(10)

        self.liste = QListWidget()
        self.liste.setObjectName('liste')
        self.liste.setMinimumHeight(140)
        self.liste.itemDoubleClicked.connect(self._charger_outil)
        v.addWidget(self.liste)

        actions = QHBoxLayout()
        actions.setSpacing(8)
        for txt, fn in (('Charger', self._charger_selection),
                        ('Supprimer', self._supprimer_selection),
                        ('.fctb…', self._exporter_fctb),
                        ('Export JSON…', self._exporter_json)):
            bb = QPushButton(txt)
            bb.setObjectName('mini')
            bb.setMinimumHeight(34)
            bb.setCursor(Qt.PointingHandCursor)
            bb.clicked.connect(fn)
            actions.addWidget(bb)
        v.addSpacing(10)
        v.addLayout(actions)

        echanges = QHBoxLayout()
        echanges.setSpacing(8)
        for txt, fn in (('↓ Lire FreeCAD…', self._importer_freecad),
                        ('↑ Écrire dans FreeCAD…', self._exporter_freecad)):
            bb = QPushButton(txt)
            bb.setObjectName('mini')
            bb.setMinimumHeight(34)
            bb.setCursor(Qt.PointingHandCursor)
            bb.clicked.connect(fn)
            echanges.addWidget(bb)
        v.addSpacing(8)
        v.addLayout(echanges)
        return carte

    # ------------------------------------------- aller-retour avec FreeCAD
    def _dossier_freecad(self):
        """Le dossier d'outils de FreeCAD, choisi une fois puis mémorisé.

        Il est VERSIONNÉ et plusieurs versions cohabitent : deviner lequel
        est le bon est un piège — trier par date désignait ici la version de
        développement alors que la machine tourne sur la stable. On fait
        donc choisir, en montrant combien d'outils chacun contient.
        """
        dossiers = FB.dossiers_outils()
        if not dossiers:
            QMessageBox.information(
                self, APP_NOM,
                "Aucune bibliothèque d'outils FreeCAD trouvée.\n\n"
                "Attendu quelque part comme :\n"
                "  ~/.local/share/FreeCAD/v1-1/CamAssets/Tools")
            return None
        if self.dossier_fc:
            for d in dossiers:
                if str(d['chemin']) == self.dossier_fc:
                    return d
        if len(dossiers) == 1:
            self.dossier_fc = str(dossiers[0]['chemin'])
            return dossiers[0]
        noms = ['%s  —  %d outils, %d bibliothèque(s)'
                % (d['version'], d['nb_outils'], d['nb_biblio']) for d in dossiers]
        choix, ok = QInputDialog.getItem(
            self, APP_NOM, "Quelle installation de FreeCAD ?", noms, 0, False)
        if not ok:
            return None
        d = dossiers[noms.index(choix)]
        self.dossier_fc = str(d['chemin'])
        self._sauver_reglages()
        return d

    def _importer_freecad(self):
        """Reprendre un outil de FreeCAD, avec ses vitesses si on les connaît."""
        d = self._dossier_freecad()
        if d is None:
            return
        libs = FB.bibliotheques(d['chemin'])
        if not libs:
            QMessageBox.information(self, APP_NOM, "Aucune bibliothèque dans %s."
                                    % d['version'])
            return
        noms = ['%s  (%d outils)' % (b['label'], len(b['outils'])) for b in libs]
        choix, ok = QInputDialog.getItem(self, APP_NOM, "Quelle bibliothèque ?",
                                         noms, 0, False)
        if not ok:
            return
        lib = libs[noms.index(choix)]
        outils = FB.outils_de(d['chemin'], lib)
        if not outils:
            QMessageBox.information(self, APP_NOM, "Cette bibliothèque est vide.")
            return
        connues = FB.vitesses_connues()
        etiquettes = []
        for o in outils:
            v = connues.get(o['fichier'])
            etiquettes.append('%s  —  Ø%g, %d dents%s'
                              % (o['name'], o['d'], o['z'],
                                 '  (vitesses connues)' if v else ''))
        choix, ok = QInputDialog.getItem(self, APP_NOM, "Quel outil reprendre ?",
                                         etiquettes, 0, False)
        if not ok:
            return
        o = outils[etiquettes.index(choix)]
        v = connues.get(o['fichier']) or {}

        # La géométrie vient de FreeCAD ; les vitesses, de nous — et si on ne
        # les connaît pas, l'appli les recalcule depuis la matière.
        self.f_d.edit.setText(('%g' % o['d']).replace('.', ','))
        self.f_z.edit.setText(str(o['z']))
        self.forme = o.get('forme', 'plat')
        for i, b in self.btn_formes.items():
            b.setChecked(i == self.forme)
        for cle, champ in (('hcoupe', self.f_hcoupe), ('lgtotale', self.f_lgtot),
                           ('queue', self.f_queue), ('extra', self.f_extra)):
            val = o.get(cle)
            champ.edit.setText(('%g' % val).replace('.', ',') if val else '')
        if v.get('mat'):
            self.mat = v['mat']
            for b in self.grp_mat.buttons():
                b.setChecked(b.text() == C.matiere(self.mat)['label'])
        self.helice = v.get('helice', 'montante')
        for i, b in self.btn_helices.items():
            b.setChecked(i == self.helice)
        self.case_plongeant.setChecked(v.get('plongeant', True))
        self.f_ae.edit.setText(str(v.get('ae', '') or ''))
        self.f_n.edit.setText(str(v.get('n', '') or ''))
        self.f_fz.edit.setText(str(o.get('fz', '') or '').replace('.', ','))
        self.f_vf.edit.clear()
        self.mode = 'avance'
        for c, b in self.btn_modes.items():
            b.setChecked(c == 'avance')
        self.e_nom.setText(o['name'])
        self.fichier_fc = o['fichier']
        self.recalculer()
        QMessageBox.information(
            self, APP_NOM,
            "« %s » repris de « %s ».\n\n%s"
            % (o['name'], lib['label'],
               "Ses vitesses étaient connues, elles sont revenues avec lui."
               if v else "FreeCAD ne garde pas les vitesses : celles-ci sont "
                         "calculées pour la matière choisie. Enregistrer l'outil "
                         "puis « Écrire dans FreeCAD » pour qu'elles soient "
                         "retenues."))

    def _exporter_freecad(self):
        """Écrire l'outil courant dans une bibliothèque FreeCAD."""
        it = self.liste.currentItem()
        if it is None:
            QMessageBox.information(self, APP_NOM,
                                    "Choisir d'abord un outil dans la bibliothèque.")
            return
        o = it.data(Qt.UserRole)
        d = self._dossier_freecad()
        if d is None:
            return
        libs = FB.bibliotheques(d['chemin'])
        noms = ['%s  (%d outils)' % (b['label'], len(b['outils'])) for b in libs] \
            + ['— dans le magasin seulement, sans bibliothèque —']
        choix, ok = QInputDialog.getItem(self, APP_NOM, "Dans quelle bibliothèque ?",
                                         noms, 0, False)
        if not ok:
            return
        idx = noms.index(choix)
        lib = libs[idx] if idx < len(libs) else None

        g = C.geometrie(o.get('d'), o.get('forme', 'plat'), o.get('hcoupe'),
                        o.get('lgtotale'), o.get('queue'), o.get('extra'),
                        o.get('extra'))
        fichier = C.fichier_outil(o['name'], g, o.get('z'), C.num(o.get('fz'), 0),
                                  o.get('helice', 'montante'),
                                  o.get('plongeant', True))
        # Les vitesses ne tiennent PAS dans le .fctb : FreeCAD vide son champ
        # libre dès qu'il le réécrit. On les garde donc à côté, rattachées au
        # nom du fichier.
        vitesses = {k: o.get(k) for k in
                    ('n', 'vf', 'plunge', 'rapidH', 'rapidV', 'ae', 'fz')}
        vitesses['mat'] = o.get('mat')
        vitesses['helice'] = o.get('helice', 'montante')
        vitesses['plongeant'] = o.get('plongeant', True)
        try:
            nom_fichier = FB.ecrire_outil(d['chemin'], fichier, lib, vitesses)
        except OSError as e:
            QMessageBox.critical(self, APP_NOM, "Écriture impossible :\n%s" % e)
            return
        QMessageBox.information(
            self, APP_NOM,
            "« %s » est dans FreeCAD (%s).\n\nFichier : %s\n%s\n\n"
            "Ses vitesses sont retenues ici, hors des fichiers de FreeCAD, "
            "qui ne sait pas les garder."
            % (o['name'], d['version'], nom_fichier,
               ('Bibliothèque : ' + lib['label']) if lib else
               'Rangé dans le magasin, sans bibliothèque.'))

    # ------------------------------------------------------------ actions
    def choisir_matiere(self, mid):
        # Repartir des conseillés : garder une broche saisie pour le bois en
        # passant à l'acier n'aurait aucun sens.
        self.mat = mid
        for f in (self.f_n, self.f_fz, self.f_vf):
            f.edit.clear()
        for b in self.grp_mat.buttons():
            b.setChecked(b.text() == C.matiere(mid)['label'])
        self.recalculer()

    def choisir_mode(self, cle):
        self.mode = cle
        for f in (self.f_n, self.f_fz, self.f_vf):
            f.edit.clear()
        for c, b in self.btn_modes.items():
            b.setChecked(c == cle)
        self.recalculer()

    def _basculer_aide_ae(self):
        self.bloc_aide_ae.setVisible(self.btn_aide_ae.isChecked())

    def _basculer_machine(self):
        ouvert = self.btn_machine.isChecked()
        self.corps_machine.setVisible(ouvert)
        self.btn_machine.setText('replier' if ouvert else 'modifier')

    def basculer_theme(self):
        self.theme = 'nuit' if self.theme == 'jour' else 'jour'
        self._appliquer_theme()
        self._sauver_reglages()

    # ------------------------------------------------------------ calcul
    def recalculer(self):
        r = C.calculer(
            mat=self.mat, d=self.f_d.valeur(), z=self.f_z.valeur(), mode=self.mode,
            n=self.f_n.valeur(), fz=self.f_fz.valeur(), vf=self.f_vf.valeur(),
            ae=self.f_ae.valeur(),
            m_min=self.f_min.valeur(), m_max=self.f_max.valeur(),
            plunge=self.f_plunge.valeur(), vf_max=self.f_vfmax.valeur())
        self.dernier = r

        n_calc = (self.mode == 'broche')
        fz_calc = (self.mode == 'copeau')
        vf_calc = (self.mode == 'avance')

        # Le champ déduit affiche le résultat ; les champs saisis gardent la
        # valeur brute, jamais formatée — on recopierait des espaces.
        if n_calc:
            self.f_n.poser(C.fmt(r['n']))
        elif not self.f_n.valeur():
            self.f_n.poser(str(int(r['rec_n'])))
        if fz_calc:
            self.f_fz.poser(('%.3f' % r['fz']).rstrip('0').rstrip('.').replace('.', ','))
        elif not self.f_fz.valeur():
            self.f_fz.poser(str(r['rec_fz']).replace('.', ','))
        if vf_calc:
            self.f_vf.poser(C.fmt(r['vf']))
        elif not self.f_vf.valeur():
            self.f_vf.poser(str(int(round(r['rec_n'] * r['z'] * r['rec_fz']))))

        for champ, calc in ((self.f_n, n_calc), (self.f_fz, fz_calc), (self.f_vf, vf_calc)):
            champ.marquer_calcule(calc)
        self.btn_reset_n.setVisible(not n_calc)
        self.btn_reset_fz.setVisible(not fz_calc)

        self.f_n.aide.setText("Déduite de l’avance et du copeau" if n_calc
                              else "Conseillé : " + C.fmt(r['rec_n']))
        # En mode « copeau », l'aide porte le VERDICT : le copeau obtenu
        # comparé au conseillé. C'est tout l'intérêt de ce sens de calcul.
        pc = round(r['fz'] / r['rec_fz'] * 100) if r['rec_fz'] else 0
        if fz_calc:
            juge = (" : la fraise frotte plus qu’elle ne coupe." if pc < 50
                    else " : ça coupe, mais on chauffe." if pc < 80
                    else " : bon copeau." if pc <= 130
                    else " : copeau épais, surveiller l’effort.")
            self.f_fz.aide.setText("Déduit de la broche et de l’avance — %d %% du "
                                   "conseillé%s" % (pc, juge))
        else:
            self.f_fz.aide.setText("Conseillé : " + str(r['rec_fz']).replace('.', ','))
        self.f_vf.aide.setText("Déduite de la broche et du copeau" if vf_calc
                               else "Ce que tu veux atteindre")
        if r['ae'] > 0:
            self.f_ae.aide.setText(
                "Reprise de contour — copeau aminci, avance ×%s"
                % str(round(r['amincissement'], 2)).replace('.', ',')
                if r['amincissement'] > 1.005
                else "Au-delà de la demi-fraise : plus d’amincissement.")
        else:
            self.f_ae.aide.setText("Vide = la fraise coupe sur tout son diamètre.")

        # L'unite est stylee EN LIGNE et non par la feuille QSS : Qt
        # n'applique pas les selecteurs de classe a l'interieur d'un texte
        # enrichi, si bien que « mm/min » s'affichait en 30 px comme le
        # chiffre et debordait de sa colonne, coupe au bord de la carte.
        p = NUIT if self.theme == 'nuit' else JOUR
        def unite(txt, taille):
            return ('<span style="font-size:%dpx; color:%s; font-weight:400">'
                    '&nbsp;%s</span>' % (taille, p['second'], txt))
        self.o_vf.setText(C.fmt(r['vf']) + unite('mm/min', 12))
        self.o_n.setText(C.fmt(r['n']) + unite('tr/min', 12))
        self.o_vz.setText(C.fmt(r['vz']) + unite('mm/min', 11))
        self.o_fpr.setText(C.fmt(r['fpr'], 2) + unite('mm/tr', 11))
        for l in (self.o_vf, self.o_n, self.o_vz, self.o_fpr):
            l.setTextFormat(Qt.RichText)

        self.o_contexte.setText(
            "Profondeur Ap %s  ·  Vc %s m/min  ·  %s"
            % (r['matiere']['ap'], C.fmt(r['vc']),
               ('ae %s mm' % str(r['ae']).replace('.', ',')) if r['ae'] > 0 else 'pleine largeur'))
        self.o_note.setText(r['matiere']['note'])

        # La géométrie : elle ne change aucun chiffre, mais elle avertit.
        g = C.geometrie(self.f_d.valeur(), self.forme,
                        self.f_hcoupe.valeur(), self.f_lgtot.valeur(),
                        self.f_queue.valeur(), self.f_extra.valeur(),
                        self.f_extra.valeur())
        self.geo = g
        extra = g['forme']['extra']
        self.f_extra.setVisible(bool(extra))
        if extra:
            self.f_extra.lbl.setText(
                '%s  <span style="color:#8b8985">(%s)</span>' % (extra[1], extra[2]))
        self.lbl_note_helice.setText(C.HELICE_PAR_ID[self.helice]['note'])
        r['avertissements'] = r['avertissements'] + C.avertissements_fraise(
            g, self.helice, self.case_plongeant.isChecked(), r['matiere']['ap'])
        self.lbl_resume_fraise.setText(
            "%s · coupe %s mm · queue %s mm · %s%s"
            % (g['forme']['label'].lower(), C.fmt(g['hauteur_coupe'], 1),
               C.fmt(g['queue'], 2), C.HELICE_PAR_ID[self.helice]['label'].lower(),
               (" · %d valeur(s) déduite(s)" % len(g['deduit'])) if g['deduit'] else ''))

        alerte = bool(r['avertissements'])
        self.o_avert.setText(' '.join(r['avertissements']))
        self.bloc_avert.setVisible(alerte)
        self.carte_resultat.setProperty('alerte', 'oui' if alerte else 'non')
        self.carte_resultat.style().unpolish(self.carte_resultat)
        self.carte_resultat.style().polish(self.carte_resultat)

        self.lbl_resume.setText(
            "%s–%s tr/min · %s mm/min · plongée %s %%"
            % (C.fmt(C.num(self.f_min.valeur(), 1000)),
               C.fmt(C.num(self.f_max.valeur(), 24000)),
               C.fmt(C.num(self.f_vfmax.valeur(), 1500)),
               C.fmt(C.num(self.f_plunge.valeur(), 35))))
        self._sauver_reglages()

    # ------------------------------------------------------- bibliothèque
    def enregistrer_outil(self):
        r = getattr(self, 'dernier', None)
        if not r:
            return
        nom = self.e_nom.text().strip() or (
            "%s · Ø%s Z%s" % (r['matiere']['label'], self.f_d.valeur(), self.f_z.valeur()))
        outil = dict(name=nom, mat=self.mat, d=self.f_d.valeur(), z=self.f_z.valeur(),
                     n=str(int(round(r['n']))), fz=str(round(r['fz'], 3)),
                     ae=self.f_ae.valeur(), vf=int(round(r['vf'])),
                     plunge=int(round(r['vz'])),
                     rapidH=int(round(C.num(self.f_rapidh.valeur(), 8000))),
                     rapidV=int(round(C.num(self.f_rapidv.valeur(), 2700))),
                     forme=self.forme, helice=self.helice,
                     plongeant=self.case_plongeant.isChecked(),
                     hcoupe=self.f_hcoupe.valeur(), lgtotale=self.f_lgtot.valeur(),
                     queue=self.f_queue.valeur(), extra=self.f_extra.valeur(),
                     sub="%s tr/min · %s mm/min" % (C.fmt(r['n']), C.fmt(r['vf'])))
        for i, o in enumerate(self.bibliotheque):
            if o['name'] == nom:
                self.bibliotheque[i] = outil
                break
        else:
            self.bibliotheque.insert(0, outil)
        self.e_nom.clear()
        self._rendre_biblio()
        self._sauver_reglages()

    def _rendre_biblio(self):
        self.liste.clear()
        self.lbl_biblio.setText('BIBLIOTHÈQUE (%d)' % len(self.bibliotheque))
        for o in self.bibliotheque:
            it = QListWidgetItem('%s\n%s' % (o['name'], o.get('sub', '')))
            it.setData(Qt.UserRole, o)
            self.liste.addItem(it)

    def _charger_selection(self):
        it = self.liste.currentItem()
        if it:
            self._charger_outil(it)

    def _charger_outil(self, item):
        o = item.data(Qt.UserRole)
        self.mat = o.get('mat', 'bois-tendre')
        self.f_d.edit.setText(str(o.get('d', '6')))
        self.f_z.edit.setText(str(o.get('z', '2')))
        self.f_n.edit.setText(str(o.get('n', '')))
        self.f_fz.edit.setText(str(o.get('fz', '')).replace('.', ','))
        # `ae` fait partie de l'outil : sans lui, un outil enregistré en
        # reprise de contour se rouvrirait avec l'avance de la pleine largeur.
        self.f_ae.edit.setText(str(o.get('ae', '') or ''))
        # La géométrie suit l'outil : sans elle, le fichier FreeCAD
        # redeviendrait une fraise déduite du seul diamètre.
        self.forme = o.get('forme', 'plat')
        self.helice = o.get('helice', 'montante')
        self.case_plongeant.setChecked(o.get('plongeant', True))
        for cle, champ in (('hcoupe', self.f_hcoupe), ('lgtotale', self.f_lgtot),
                           ('queue', self.f_queue), ('extra', self.f_extra)):
            champ.edit.setText(str(o.get(cle, '') or ''))
        for i, b in self.btn_formes.items():
            b.setChecked(i == self.forme)
        for i, b in self.btn_helices.items():
            b.setChecked(i == self.helice)
        self.f_vf.edit.clear()
        self.mode = 'avance'
        for c, b in self.btn_modes.items():
            b.setChecked(c == 'avance')
        for b in self.grp_mat.buttons():
            b.setChecked(b.text() == C.matiere(self.mat)['label'])
        self.recalculer()

    def _supprimer_selection(self):
        i = self.liste.currentRow()
        if i >= 0:
            del self.bibliotheque[i]
            self._rendre_biblio()
            self._sauver_reglages()

    def _exporter_json(self):
        """Écrit toute la bibliothèque, telle que la macro FreeCAD l'attend.

        C'est ce fichier — et non le .fctb — que `macro_tool_controller.py`
        lit pour remplir un Tool Controller : le .fctb porte la géométrie de
        la fraise, jamais les vitesses. Même nom par défaut que l'appli web,
        pour que la macro le retrouve sans qu'on ait à chercher.
        """
        if not self.bibliotheque:
            QMessageBox.information(self, APP_NOM,
                                    "La bibliothèque est vide : enregistrer "
                                    "d'abord au moins un outil.")
            return
        depart = Path.home() / 'Téléchargements'
        if not depart.is_dir():
            depart = Path.home() / 'Downloads'
        if not depart.is_dir():
            depart = Path.home()
        chemin, _ = QFileDialog.getSaveFileName(
            self, "Exporter la bibliothèque d'outils",
            str(depart / 'outils-vitesses-coupe.json'),
            "Bibliothèque d'outils (*.json)")
        if not chemin:
            return
        try:
            Path(chemin).write_text(
                json.dumps(self.bibliotheque, ensure_ascii=False, indent=2) + '\n',
                encoding='utf-8')
        except OSError as e:
            QMessageBox.critical(self, APP_NOM, "Écriture impossible :\n%s" % e)
            return
        QMessageBox.information(
            self, APP_NOM,
            "%d outil(s) écrits dans :\n%s\n\nDans FreeCAD : Macro → "
            "macro_tool_controller.py, qui lira ce fichier et posera les cinq "
            "vitesses sur le Tool Controller du Job."
            % (len(self.bibliotheque), chemin))

    def _exporter_fctb(self):
        it = self.liste.currentItem()
        if not it:
            QMessageBox.information(self, APP_NOM,
                                    "Choisir d'abord un outil dans la bibliothèque.")
            return
        o = it.data(Qt.UserRole)
        # Le fichier décrit la fraise TELLE QU'ELLE EST quand on l'a
        # renseignée — le noyau porte cette construction, partagée avec
        # l'appli web.
        g = C.geometrie(o.get('d'), o.get('forme', 'plat'), o.get('hcoupe'),
                        o.get('lgtotale'), o.get('queue'), o.get('extra'),
                        o.get('extra'))
        contenu = json.dumps(
            C.fichier_outil(o['name'], g, o.get('z'), C.num(o.get('fz'), 0),
                            o.get('helice', 'montante'), o.get('plongeant', True)),
            ensure_ascii=False, indent=2)
        defaut = ''.join(ch if ch.isalnum() else '_' for ch in o['name']) + '.fctb'
        chemin, _ = QFileDialog.getSaveFileName(
            self, "Enregistrer le fichier d'outil FreeCAD", defaut,
            "Outil FreeCAD (*.fctb)")
        if not chemin:
            return
        Path(chemin).write_text(contenu + '\n', encoding='utf-8')
        QMessageBox.information(
            self, APP_NOM,
            "Écrit : %s\n\nUn .fctb ne peut pas porter de vitesses : il décrit la "
            "fraise. Les cinq valeurs ci-dessous vont dans le Tool Controller du "
            "Job — ou bien lancez la macro macro_tool_controller.py, qui les pose "
            "toute seule à partir de la bibliothèque exportée.\n\n"
            "  SpindleSpeed = %s\n  HorizFeed  = %s mm/min\n  VertFeed   = %s mm/min\n"
            "  HorizRapid = %s mm/min\n  VertRapid  = %s mm/min"
            % (Path(chemin).name, o.get('n'), o.get('vf'), o.get('plunge'),
               o.get('rapidH', 8000), o.get('rapidV', 2700)))

    # ------------------------------------------------------- persistance
    def _sauver_reglages(self):
        try:
            DOSSIER_CONF.mkdir(parents=True, exist_ok=True)
            FICHIER_CONF.write_text(json.dumps({
                'version': VERSION, 'theme': self.theme,
                'machine': {'min': self.f_min.valeur(), 'max': self.f_max.valeur(),
                            'plunge': self.f_plunge.valeur(), 'vfMax': self.f_vfmax.valeur(),
                            'rapidH': self.f_rapidh.valeur(), 'rapidV': self.f_rapidv.valeur()},
                'bibliotheque': self.bibliotheque,
                'dossier_freecad': self.dossier_fc,
            }, ensure_ascii=False, indent=2), encoding='utf-8')
        except OSError:
            pass          # une appli de calcul ne doit pas mourir d'un disque plein

    def _charger_reglages(self):
        try:
            if not FICHIER_CONF.exists():
                return
            d = json.loads(FICHIER_CONF.read_text(encoding='utf-8'))
        except (OSError, ValueError):
            return
        if d.get('theme') in ('jour', 'nuit'):
            self.theme = d['theme']
        m = d.get('machine') or {}
        for cle, champ in (('min', self.f_min), ('max', self.f_max),
                           ('plunge', self.f_plunge), ('vfMax', self.f_vfmax),
                           ('rapidH', self.f_rapidh), ('rapidV', self.f_rapidv)):
            if m.get(cle):
                champ.edit.setText(str(m[cle]))
        self.bibliotheque = d.get('bibliotheque') or []
        self.dossier_fc = d.get('dossier_freecad') or ''
        self._rendre_biblio()

    # ------------------------------------------------------------ thème
    def _appliquer_theme(self):
        p = NUIT if self.theme == 'nuit' else JOUR
        self.btn_theme.setText('☀  jour' if self.theme == 'nuit' else '☾  nuit')
        self.setStyleSheet(FEUILLE % dict(p, mono=self.mono, sans=self.sans))
        if hasattr(self, 'carte_resultat'):
            for w in (self.carte_resultat,):
                w.style().unpolish(w)
                w.style().polish(w)


# =========================================================================
#  La feuille de style — mêmes valeurs que l'appli web
# =========================================================================
FEUILLE = """
QMainWindow, QWidget { background: %(page)s; color: %(txt)s;
    font-family: '%(sans)s'; font-size: 14px; }
QScrollArea, QScrollArea > QWidget > QWidget { background: transparent; }

QLabel#titre { font-family: '%(mono)s'; font-size: 17px; font-weight: 700;
    color: %(txt_strong)s; }
QLabel#sousTitre { font-size: 12.5px; color: %(second)s; }
QLabel#sectTitre { font-family: '%(mono)s'; font-size: 10px; letter-spacing: 1.4px;
    color: %(section)s; }
QLabel#famille { font-size: 11.5px; color: %(section)s; }
QLabel#labelChamp { font-size: 13px; color: %(label)s; }
QLabel#aide { font-size: 11.5px; color: %(help)s; }
QLabel#resume { font-family: '%(mono)s'; font-size: 12px; color: %(second)s; }
QLabel#contexte { font-family: '%(mono)s'; font-size: 12px; color: %(second)s; }
QLabel#note { font-size: 12.5px; color: %(second)s; }
QLabel#valGrande { font-family: '%(mono)s'; font-size: 30px; font-weight: 700;
    color: %(accent_ink)s; }
QLabel#valPetite { font-family: '%(mono)s'; font-size: 20px; font-weight: 500;
    color: %(txt)s; }
QLabel#blocAide { background: %(calc)s; border: 1px solid %(card_bd)s;
    border-radius: 10px; padding: 16px; font-size: 13px; color: %(second)s; }

QLineEdit { background: %(field)s; border: 1px solid %(field_bd)s; border-radius: 9px;
    padding: 0 16px; font-family: '%(mono)s'; font-size: 15px; color: %(txt_strong)s;
    selection-background-color: %(accent)s; selection-color: %(on_accent)s; }
QLineEdit:focus { border: 1px solid %(accent)s; }
QLineEdit[calcule="oui"] { background: %(calc)s; border: 1px dashed %(accent)s;
    color: %(accent_ink)s; }

QPushButton#choix { background: %(field)s; border: 1px solid %(field_bd)s;
    border-radius: 9px; font-family: '%(mono)s'; font-size: 13px; color: %(btn_off)s;
    padding: 0 12px; }
QPushButton#choix:hover { border: 1px solid %(accent)s; }
QPushButton#choix:checked { background: %(accent)s; border: 1px solid %(accent)s;
    color: %(on_accent)s; font-weight: 500; }
QPushButton#reset { background: %(field)s; border: 1px solid %(field_bd)s;
    border-radius: 9px; font-family: '%(mono)s'; font-size: 15px; color: %(second)s; }
QPushButton#reset:hover { color: %(accent_ink)s; border: 1px solid %(accent)s; }
QPushButton#primaire { background: %(accent)s; border: 1px solid %(accent)s;
    border-radius: 9px; font-family: '%(mono)s'; font-size: 13px; font-weight: 700;
    color: %(on_accent)s; padding: 0 18px; }
QPushButton#mini { background: transparent; border: 1px solid %(field_bd)s;
    border-radius: 8px; font-family: '%(mono)s'; font-size: 11.5px;
    color: %(second)s; padding: 0 12px; }
QPushButton#mini:hover { color: %(accent_ink)s; border: 1px solid %(accent)s; }
QPushButton#btnTheme { background: %(field)s; border: 1px solid %(field_bd)s;
    border-radius: 9px; font-family: '%(mono)s'; font-size: 12px; color: %(second)s;
    padding: 6px 12px; }
QPushButton#btnTheme:hover { color: %(txt)s; }
QPushButton#bascule { background: transparent; border: none;
    font-family: '%(mono)s'; font-size: 12px; color: %(help)s; }
QPushButton#pastilleAide { background: %(seg)s; border: 1px solid %(field_bd)s;
    border-radius: 11px; font-family: '%(mono)s'; font-size: 11.5px; color: %(second)s; }

QFrame#carte { background: %(card)s; border: 1px solid %(card_bd)s; border-radius: 12px; }
QFrame#resultat { background: %(result)s; border: 1px solid %(result_bd)s;
    border-radius: 14px; }
QFrame#resultat[alerte="oui"] { border: 1px solid %(result_bd_warn)s; }
QFrame#avert { background: %(warn_bg)s; border: none; border-top: 1px solid %(result_bd_warn)s; }
QFrame#barreAvert { background: %(warn_bar)s; border-radius: 3px; }
QLabel#titreAvert { font-family: '%(mono)s'; font-size: 10px; letter-spacing: 1.4px;
    color: %(warn_title)s; }
QLabel#texteAvert { font-size: 13px; color: %(warn_txt)s; }

QListWidget#liste { background: %(field)s; border: 1px solid %(field_bd)s;
    border-radius: 9px; font-family: '%(mono)s'; font-size: 12px; color: %(txt)s;
    padding: 4px; }
QListWidget#liste::item { padding: 8px; border-radius: 6px; }
QListWidget#liste::item:selected { background: %(accent)s; color: %(on_accent)s; }
QToolTip { background: %(card)s; color: %(txt)s; border: 1px solid %(card_bd)s; padding: 6px; }
"""


def main():
    app = QApplication(sys.argv)
    app.setApplicationName(APP_NOM)
    app.setApplicationVersion(VERSION)
    f = Fenetre()
    f.show()
    sys.exit(app.exec())


if __name__ == '__main__':
    main()
