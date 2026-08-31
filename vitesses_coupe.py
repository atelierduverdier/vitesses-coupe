#!/usr/bin/env python3
# =========================================================================
# vitesses_coupe.py — l'appli de bureau, en PySide6
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
    QHBoxLayout, QLabel, QLineEdit, QListWidget, QListWidgetItem, QMainWindow,
    QMessageBox, QPushButton, QScrollArea, QSizePolicy, QVBoxLayout, QWidget)

sys.path.insert(0, str(Path(__file__).resolve().parent))
import coupe_noyau as C

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
        self.bibliotheque = []
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
        g.addWidget(self.f_min, 1, 0)
        g.addWidget(self.f_max, 1, 1)
        g.addWidget(self.f_plunge, 2, 0)
        g.addWidget(self.f_vfmax, 2, 1)
        for f in (self.f_min, self.f_max, self.f_plunge, self.f_vfmax):
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
                        ('Exporter .fctb…', self._exporter_fctb)):
            bb = QPushButton(txt)
            bb.setObjectName('mini')
            bb.setMinimumHeight(34)
            bb.setCursor(Qt.PointingHandCursor)
            bb.clicked.connect(fn)
            actions.addWidget(bb)
        v.addSpacing(10)
        v.addLayout(actions)
        return carte

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

    def _exporter_fctb(self):
        it = self.liste.currentItem()
        if not it:
            QMessageBox.information(self, APP_NOM,
                                    "Choisir d'abord un outil dans la bibliothèque.")
            return
        o = it.data(Qt.UserRole)
        d = C.num(o.get('d'), 6)
        contenu = json.dumps({
            'version': 2, 'name': o['name'], 'shape': 'endmill.fcstd',
            'parameter': {
                'Diameter': '%s mm' % d,
                'Flutes': max(1, round(C.num(o.get('z'), 2))),
                'Chipload': '%s mm' % C.num(o.get('fz'), 0),
                'CuttingEdgeHeight': '%.2f mm' % (d * 3),
                'Length': '%.2f mm' % (d * 8),
                'ShankDiameter': '%s mm' % d,
                'Material': 'Carbide'},
            'attribute': {}}, ensure_ascii=False, indent=2)
        defaut = ''.join(ch if ch.isalnum() else '_' for ch in o['name']) + '.fctb'
        chemin, _ = QFileDialog.getSaveFileName(
            self, "Enregistrer le fichier d'outil FreeCAD", defaut,
            "Outil FreeCAD (*.fctb)")
        if not chemin:
            return
        Path(chemin).write_text(contenu + '\n', encoding='utf-8')
        QMessageBox.information(
            self, APP_NOM,
            "Écrit : %s\n\nLe .fctb porte la géométrie de la fraise. Les vitesses "
            "vont dans le Tool Controller du Job :\n"
            "  SpindleSpeed = %s\n  HorizFeed = %s mm/min\n  VertFeed = %s mm/min"
            % (Path(chemin).name, o.get('n'), o.get('vf'), o.get('plunge')))

    # ------------------------------------------------------- persistance
    def _sauver_reglages(self):
        try:
            DOSSIER_CONF.mkdir(parents=True, exist_ok=True)
            FICHIER_CONF.write_text(json.dumps({
                'version': VERSION, 'theme': self.theme,
                'machine': {'min': self.f_min.valeur(), 'max': self.f_max.valeur(),
                            'plunge': self.f_plunge.valeur(), 'vfMax': self.f_vfmax.valeur()},
                'bibliotheque': self.bibliotheque,
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
                           ('plunge', self.f_plunge), ('vfMax', self.f_vfmax)):
            if m.get(cle):
                champ.edit.setText(str(m[cle]))
        self.bibliotheque = d.get('bibliotheque') or []
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
