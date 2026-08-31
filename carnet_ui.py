#!/usr/bin/env python3
# =========================================================================
# carnet_ui.py — l'interface du carnet d'essais, greffée sur l'appli
# © Atelier du Verdier — licence LGPL-2.1-or-later (cf. LICENSE).
# =========================================================================
# Deux fenêtres :
#   FenetreCarnet   — consulter : filtrer, chercher, voir le détail et la
#                      photo d'un essai, comparer son copeau à la théorie.
#   FormulaireEssai — noter ou compléter un essai (même formulaire pour
#                      les deux, préempli différemment).
#
# FenetreCarnet est une fenêtre ANNEXE NON MODALE : consulter le carnet ne
# doit pas empêcher de retoucher le calculateur juste à côté — c'est même
# l'intérêt. « Noter cet essai » relit l'état du calculateur au moment du
# clic, pas celui d'il y a cinq minutes.
#
# Ce module ne parle au carnet QUE par `carnet_noyau` (aucune écriture
# directe de JSON ici) et ne connaît pas `vitesses_coupe` : il reçoit tout
# ce qu'il faut (palette, feuille de style, état du calculateur) en
# paramètre. La feuille de style vient donc de la fenêtre principale, pas
# d'une copie : dupliquer JOUR/NUIT/FEUILLE ici serait le même risque de
# dérive que la version qui traînait dans quatre fichiers à la fois.
#
# Rappel payé ailleurs dans ce dépôt : QSS ne style PAS le texte enrichi.
# Toutes les mises en valeur ci-dessous passent par un `objectName` déjà
# reconnu de la feuille de style de l'appli, jamais par du HTML en ligne.
# =========================================================================

import datetime
from pathlib import Path

from PySide6.QtCore import Qt
from PySide6.QtGui import QColor, QPixmap
from PySide6.QtWidgets import (
    QComboBox, QDialog, QFileDialog, QFrame, QGridLayout, QHBoxLayout,
    QLabel, QLineEdit, QListWidget, QListWidgetItem, QMessageBox,
    QPushButton, QVBoxLayout, QWidget)

import carnet_noyau as K
import coupe_noyau as C


# =========================================================================
#  Petits outils partagés par les deux fenêtres
# =========================================================================
def titre_section(texte):
    l = QLabel(texte.upper())
    l.setObjectName('sectTitre')
    return l


def _champ(libelle, widget):
    """Un libellé au-dessus d'un widget de saisie — la version légère du
    `Champ` de vitesses_coupe.py, sans la ligne d'aide (pas besoin ici)."""
    conteneur = QWidget()
    v = QVBoxLayout(conteneur)
    v.setContentsMargins(0, 0, 0, 0)
    v.setSpacing(5)
    lbl = QLabel(libelle)
    lbl.setObjectName('labelChamp')
    v.addWidget(lbl)
    v.addWidget(widget)
    return conteneur


def _peupler_combo_matieres(combo, option_vide):
    combo.addItem(option_vide, '')
    for _famille, items in C.MATIERES:
        for m in items:
            combo.addItem(m['label'], m['id'])


def _mm(x, dec=2):
    """Un nombre sans zéros inutiles, virgule française — `coupe_noyau.fmt`
    arrondit à l'entier par défaut, ce qui écraserait un Ø 6,35 ou un
    Ae 0,3."""
    if not x:
        return ''
    s = ('%.*f' % (dec, x)).rstrip('0').rstrip('.')
    return s.replace('.', ',')


def _entier(x):
    return str(int(round(x))) if x else ''


def _date_fr(iso):
    try:
        return datetime.date.fromisoformat(iso).strftime('%d/%m/%Y')
    except (TypeError, ValueError):
        return iso or ''


def _libelle_matiere(essai):
    m = C.PAR_ID.get(essai.get('matiere'))
    essence = essai.get('essence')
    if m and essence:
        return '%s (%s)' % (essence, m['label'])
    if essence:
        return essence
    if m:
        return m['label']
    return 'matière non précisée'


def _juge_copeau(pc):
    """Même repère que le calculateur (`vitesses_coupe.recalculer`), au
    passé : ici on relit un essai déjà usiné, pas un réglage en cours."""
    if pc < 50:
        return "la fraise frottait plus qu'elle ne coupait."
    if pc < 80:
        return "ça coupait, mais ça chauffait."
    if pc <= 130:
        return "bon copeau."
    return "copeau épais — l'effort était à surveiller."


# =========================================================================
#  La photo d'un essai
# =========================================================================
class CadrePhoto(QFrame):
    """Un cadre VIDE si l'essai n'a pas de photo, ou si le fichier a
    disparu du disque : `carnet_noyau.chemin_photo` ne garantit rien, à
    l'interface de ne jamais planter dessus."""

    LARGEUR, HAUTEUR = 220, 180

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName('carte')
        self.setFixedSize(self.LARGEUR, self.HAUTEUR)
        v = QVBoxLayout(self)
        v.setContentsMargins(8, 8, 8, 8)
        self._label = QLabel('(pas de photo)')
        self._label.setObjectName('aide')
        self._label.setAlignment(Qt.AlignCenter)
        self._label.setWordWrap(True)
        v.addWidget(self._label)

    def definir(self, chemin):
        """`chemin` : un `Path`, une chaîne, ou None."""
        chemin = Path(chemin) if chemin else None
        if not chemin or not chemin.is_file():
            self._label.setPixmap(QPixmap())
            self._label.setText('(pas de photo)')
            return
        pix = QPixmap(str(chemin))
        if pix.isNull():
            self._label.setPixmap(QPixmap())
            self._label.setText('(photo illisible)')
            return
        self._label.setText('')
        marge = 16
        self._label.setPixmap(pix.scaled(
            self.LARGEUR - marge, self.HAUTEUR - marge,
            Qt.KeepAspectRatio, Qt.SmoothTransformation))


# =========================================================================
#  Noter ou compléter un essai — même formulaire pour les deux
# =========================================================================
class FormulaireEssai(QDialog):
    """`essai_existant` (dict complet) déclenche le mode correction ;
    sinon `valeurs_defaut` préremplit un essai neuf — typiquement l'état
    courant du calculateur. `feuille` est la feuille de style DÉJÀ rendue
    par la fenêtre principale : ce dialogue est une fenêtre à part, Qt ne
    lui propage pas le style de son parent tout seul."""

    def __init__(self, parent, titre, feuille, dossier=None,
                 essai_existant=None, valeurs_defaut=None):
        super().__init__(parent)
        self.dossier = dossier
        self.essai_existant = essai_existant
        self.resultat = None
        self.photo_choisie = None
        self.setWindowTitle(titre)
        self.setStyleSheet(feuille)
        self._construire(essai_existant or valeurs_defaut or {})

    def _construire(self, depart):
        racine = QVBoxLayout(self)
        racine.setContentsMargins(20, 20, 20, 20)
        racine.setSpacing(14)

        grille = QGridLayout()
        grille.setHorizontalSpacing(14)
        grille.setVerticalSpacing(14)

        self.e_date = QLineEdit(depart.get('date')
                                or datetime.date.today().isoformat())
        self.combo_matiere = QComboBox()
        _peupler_combo_matieres(self.combo_matiere, '— non précisée —')
        i = self.combo_matiere.findData(depart.get('matiere') or '')
        self.combo_matiere.setCurrentIndex(i if i >= 0 else 0)
        self.e_essence = QLineEdit(depart.get('essence') or '')
        self.e_essence.setPlaceholderText('chêne de récup…')

        self.combo_operation = QComboBox()
        self.combo_operation.setEditable(True)
        self.combo_operation.addItems(K.OPERATIONS)
        self.combo_operation.setCurrentText(depart.get('operation') or '')
        self.e_travail = QLineEdit(depart.get('travail') or '')
        self.e_travail.setPlaceholderText('porte hammam…')
        self.e_fraise = QLineEdit(depart.get('fraise') or '')
        self.e_fraise.setPlaceholderText("nom ou description de l'outil")

        self.e_d = QLineEdit(_mm(depart.get('d')))
        self.e_z = QLineEdit(str(depart.get('z')) if depart.get('z') else '')
        indice_mat = C.PAR_ID.get(depart.get('matiere'))
        self.e_ap = QLineEdit(_mm(depart.get('ap')))
        self.e_ap.setPlaceholderText(indice_mat['ap'] if indice_mat else '')
        self.e_n = QLineEdit(_entier(depart.get('n')))
        self.e_vf = QLineEdit(_entier(depart.get('vf')))
        self.e_ae = QLineEdit(_mm(depart.get('ae')))
        self.e_ae.setPlaceholderText('pleine largeur')

        self.e_verdict = QLineEdit(depart.get('verdict') or '')
        self.e_verdict.setPlaceholderText('propre, ça brûle, ras…')
        self.e_note = QLineEdit(depart.get('note') or '')
        self.e_note.setPlaceholderText('conditions, détails…')

        for w in (self.e_date, self.combo_matiere, self.e_essence,
                  self.combo_operation, self.e_travail, self.e_fraise,
                  self.e_d, self.e_z, self.e_ap, self.e_n, self.e_vf,
                  self.e_ae, self.e_verdict, self.e_note):
            w.setMinimumHeight(40)

        grille.addWidget(_champ('Date', self.e_date), 0, 0)
        grille.addWidget(_champ('Matière', self.combo_matiere), 0, 1)
        grille.addWidget(_champ('Essence', self.e_essence), 0, 2)
        grille.addWidget(_champ('Opération', self.combo_operation), 1, 0)
        grille.addWidget(_champ('Travail', self.e_travail), 1, 1)
        grille.addWidget(_champ('Fraise', self.e_fraise), 1, 2)
        grille.addWidget(_champ('Diamètre (mm)', self.e_d), 2, 0)
        grille.addWidget(_champ('Dents (Z)', self.e_z), 2, 1)
        grille.addWidget(_champ('Ap (mm)', self.e_ap), 2, 2)
        grille.addWidget(_champ('Broche (tr/min)', self.e_n), 3, 0)
        grille.addWidget(_champ('Avance (mm/min)', self.e_vf), 3, 1)
        grille.addWidget(_champ('Ae (mm)', self.e_ae), 3, 2)
        racine.addLayout(grille)
        racine.addWidget(_champ('Verdict', self.e_verdict))
        racine.addWidget(_champ('Note', self.e_note))

        ligne_photo = QHBoxLayout()
        self.cadre_photo = CadrePhoto()
        ligne_photo.addWidget(self.cadre_photo)
        bloc_photo = QVBoxLayout()
        bloc_photo.setSpacing(8)
        bloc_photo.addWidget(titre_section('Photo'))
        self.lbl_photo = QLabel('(aucune)')
        self.lbl_photo.setObjectName('aide')
        self.lbl_photo.setWordWrap(True)
        btn_photo = QPushButton('Choisir une photo…')
        btn_photo.setObjectName('mini')
        btn_photo.setCursor(Qt.PointingHandCursor)
        btn_photo.clicked.connect(self._choisir_photo)
        bloc_photo.addWidget(self.lbl_photo)
        bloc_photo.addWidget(btn_photo, 0, Qt.AlignLeft)
        bloc_photo.addStretch(1)
        ligne_photo.addLayout(bloc_photo, 1)
        racine.addLayout(ligne_photo)

        photo_actuelle = (K.chemin_photo(self.essai_existant, self.dossier)
                          if self.essai_existant else None)
        self.cadre_photo.definir(photo_actuelle)
        if photo_actuelle:
            self.lbl_photo.setText(photo_actuelle.name)

        boutons = QHBoxLayout()
        boutons.addStretch(1)
        btn_annuler = QPushButton('Annuler')
        btn_annuler.setObjectName('mini')
        btn_annuler.setMinimumHeight(40)
        btn_annuler.setCursor(Qt.PointingHandCursor)
        btn_annuler.clicked.connect(self.reject)
        btn_enregistrer = QPushButton('Enregistrer')
        btn_enregistrer.setObjectName('primaire')
        btn_enregistrer.setMinimumHeight(44)
        btn_enregistrer.setCursor(Qt.PointingHandCursor)
        btn_enregistrer.clicked.connect(self._valider)
        boutons.addWidget(btn_annuler)
        boutons.addWidget(btn_enregistrer)
        racine.addLayout(boutons)

    def _choisir_photo(self):
        chemin, _ = QFileDialog.getOpenFileName(
            self, 'Choisir une photo', str(Path.home()),
            'Images (*.jpg *.jpeg *.png *.webp *.heic *.JPG *.JPEG *.PNG)')
        if not chemin:
            return
        self.photo_choisie = chemin
        self.cadre_photo.definir(Path(chemin))
        self.lbl_photo.setText(Path(chemin).name)

    def _valider(self):
        champs = dict(
            date=self.e_date.text().strip(),
            matiere=self.combo_matiere.currentData() or '',
            essence=self.e_essence.text(),
            operation=self.combo_operation.currentText(),
            travail=self.e_travail.text(),
            fraise=self.e_fraise.text(),
            d=self.e_d.text(), z=self.e_z.text(), n=self.e_n.text(),
            vf=self.e_vf.text(), ap=self.e_ap.text(), ae=self.e_ae.text(),
            verdict=self.e_verdict.text(), note=self.e_note.text())
        try:
            if self.essai_existant is None:
                self.resultat = K.ajouter(champs, photo=self.photo_choisie,
                                          dossier=self.dossier)
            else:
                self.resultat = K.completer(
                    self.essai_existant['id'], photo=self.photo_choisie,
                    dossier=self.dossier, **champs)
        except (ValueError, KeyError) as e:
            QMessageBox.warning(self, self.windowTitle(), str(e))
            return
        self.accept()


# =========================================================================
#  Consulter le carnet
# =========================================================================
class FenetreCarnet(QDialog):
    """`principale` est la fenêtre `Fenetre` de vitesses_coupe.py : ce
    module ne l'importe pas (pour éviter la boucle d'import — c'est elle
    qui importe carnet_ui), il se contente de lire ce dont il a besoin
    dessus (thème, champs machine, état du calculateur) à l'appel."""

    def __init__(self, principale, dossier=None):
        super().__init__(principale)
        self.principale = principale
        self.dossier = dossier
        self.essais = []
        self.essai_affiche = None
        self.erreur = None
        self.palette_active = {}
        self.setWindowTitle("Carnet d'essais")
        self.resize(920, 580)
        self._construire()
        self.rafraichir_theme()
        self._charger()

    # ---------------------------------------------------------------- UI
    def _construire(self):
        racine = QVBoxLayout(self)
        racine.setContentsMargins(20, 20, 20, 20)
        racine.setSpacing(14)

        self.bandeau_erreur = QFrame()
        self.bandeau_erreur.setObjectName('avert')
        vb = QVBoxLayout(self.bandeau_erreur)
        vb.setContentsMargins(20, 16, 20, 16)
        vb.setSpacing(6)
        t = QLabel('CARNET ILLISIBLE')
        t.setObjectName('titreAvert')
        self.lbl_erreur = QLabel('')
        self.lbl_erreur.setObjectName('texteAvert')
        self.lbl_erreur.setWordWrap(True)
        vb.addWidget(t)
        vb.addWidget(self.lbl_erreur)
        self.bandeau_erreur.hide()
        racine.addWidget(self.bandeau_erreur)

        corps = QHBoxLayout()
        corps.setSpacing(20)
        racine.addLayout(corps, 1)

        # --- gauche : filtre + liste ----------------------------------
        gauche = QVBoxLayout()
        gauche.setSpacing(10)
        gauche.addWidget(titre_section('Essais'))

        ligne_filtre = QHBoxLayout()
        ligne_filtre.setSpacing(10)
        self.combo_matiere = QComboBox()
        _peupler_combo_matieres(self.combo_matiere, 'Toutes les matières')
        self.combo_matiere.setMinimumHeight(38)
        self.champ_diametre = QLineEdit()
        self.champ_diametre.setPlaceholderText('Ø visé')
        self.champ_diametre.setFixedWidth(90)
        self.champ_diametre.setMinimumHeight(38)
        ligne_filtre.addWidget(self.combo_matiere, 1)
        ligne_filtre.addWidget(self.champ_diametre, 0)
        gauche.addLayout(ligne_filtre)
        # Connecter APRÈS avoir peuplé : le premier `addItem` d'un combo vide
        # émet déjà `currentIndexChanged`, et `self.liste` n'existe pas encore.
        self.combo_matiere.currentIndexChanged.connect(self._rafraichir_liste)
        self.champ_diametre.textEdited.connect(self._rafraichir_liste)

        self.champ_recherche = QLineEdit()
        self.champ_recherche.setPlaceholderText('Rechercher : chêne, ça brûle…')
        self.champ_recherche.setMinimumHeight(38)
        self.champ_recherche.textEdited.connect(self._rafraichir_liste)
        gauche.addWidget(self.champ_recherche)

        self.liste = QListWidget()
        self.liste.setObjectName('liste')
        self.liste.setMinimumWidth(320)
        self.liste.currentItemChanged.connect(self._selection_changee)
        self.liste.itemDoubleClicked.connect(self._completer_essai)
        gauche.addWidget(self.liste, 1)

        self.btn_noter = QPushButton('+ Noter un essai')
        self.btn_noter.setObjectName('primaire')
        self.btn_noter.setMinimumHeight(44)
        self.btn_noter.setCursor(Qt.PointingHandCursor)
        self.btn_noter.clicked.connect(self._noter_essai)
        gauche.addWidget(self.btn_noter)

        hote_gauche = QWidget()
        hote_gauche.setLayout(gauche)
        corps.addWidget(hote_gauche, 1)

        # --- droite : détail --------------------------------------------
        droite = QVBoxLayout()
        droite.setSpacing(10)
        droite.addWidget(titre_section('Détail'))

        entete_detail = QHBoxLayout()
        entete_detail.setSpacing(14)
        self.cadre_photo = CadrePhoto()
        entete_detail.addWidget(self.cadre_photo)
        bloc_titre = QVBoxLayout()
        bloc_titre.setSpacing(6)
        self.lbl_titre_detail = QLabel('Choisir un essai dans la liste.')
        self.lbl_titre_detail.setObjectName('valPetite')
        self.lbl_titre_detail.setWordWrap(True)
        self.lbl_sous_detail = QLabel('')
        self.lbl_sous_detail.setObjectName('aide')
        self.lbl_sous_detail.setWordWrap(True)
        self.lbl_cotes_detail = QLabel('')
        self.lbl_cotes_detail.setObjectName('resume')
        self.lbl_cotes_detail.setWordWrap(True)
        bloc_titre.addWidget(self.lbl_titre_detail)
        bloc_titre.addWidget(self.lbl_sous_detail)
        bloc_titre.addWidget(self.lbl_cotes_detail)
        bloc_titre.addStretch(1)
        entete_detail.addLayout(bloc_titre, 1)
        droite.addLayout(entete_detail)

        self.lbl_verdict_detail = QLabel('')
        self.lbl_verdict_detail.setWordWrap(True)
        droite.addWidget(self.lbl_verdict_detail)
        self.lbl_note_detail = QLabel('')
        self.lbl_note_detail.setObjectName('note')
        self.lbl_note_detail.setWordWrap(True)
        droite.addWidget(self.lbl_note_detail)

        carte_copeau = QFrame()
        carte_copeau.setObjectName('carte')
        vc = QVBoxLayout(carte_copeau)
        vc.setContentsMargins(18, 14, 18, 14)
        vc.setSpacing(4)
        vc.addWidget(titre_section('Rapport de copeau'))
        self.lbl_copeau = QLabel('—')
        self.lbl_copeau.setObjectName('valGrande')
        vc.addWidget(self.lbl_copeau)
        self.lbl_copeau_note = QLabel('')
        self.lbl_copeau_note.setObjectName('aide')
        self.lbl_copeau_note.setWordWrap(True)
        vc.addWidget(self.lbl_copeau_note)
        droite.addWidget(carte_copeau)
        droite.addStretch(1)

        actions_detail = QHBoxLayout()
        actions_detail.setSpacing(8)
        self.btn_completer = QPushButton('Compléter…')
        self.btn_completer.setObjectName('mini')
        self.btn_completer.setMinimumHeight(36)
        self.btn_completer.setCursor(Qt.PointingHandCursor)
        self.btn_completer.clicked.connect(self._completer_essai)
        self.btn_supprimer = QPushButton('Supprimer')
        self.btn_supprimer.setObjectName('mini')
        self.btn_supprimer.setMinimumHeight(36)
        self.btn_supprimer.setCursor(Qt.PointingHandCursor)
        self.btn_supprimer.clicked.connect(self._supprimer_essai)
        for b in (self.btn_completer, self.btn_supprimer):
            b.setEnabled(False)
            actions_detail.addWidget(b)
        droite.addLayout(actions_detail)

        hote_droite = QWidget()
        hote_droite.setLayout(droite)
        corps.addWidget(hote_droite, 1)

    # ------------------------------------------------------------ thème
    def rafraichir_theme(self):
        feuille, palette = self.principale.contexte_theme()
        self.setStyleSheet(feuille)
        self.palette_active = palette
        # QListWidgetItem n'est pas un QWidget : sa couleur est posée à la
        # main (cf. `_rafraichir_liste`), donc à rejouer après un thème.
        self._rafraichir_liste()

    # ------------------------------------------------------ le calculateur
    def preremplir_depuis_calculateur(self):
        """Rouvrir le carnet doit refléter l'état ACTUEL du calculateur,
        pas celui de la dernière ouverture — c'est tout l'intérêt du
        panneau : il sait déjà ce qu'on s'apprête à fraiser."""
        fen = self.principale
        i = self.combo_matiere.findData(fen.mat)
        self.combo_matiere.setCurrentIndex(i if i >= 0 else 0)
        r = getattr(fen, 'dernier', None)
        self.champ_diametre.setText(_mm(r.get('d')) if r else '')
        self.champ_recherche.clear()
        self._charger()

    # --------------------------------------------------------- le carnet
    def _charger(self):
        try:
            self.essais = K.charger(self.dossier)
            self.erreur = None
        except ValueError as e:
            self.essais = []
            self.erreur = str(e)
        self._rafraichir_liste()
        self._afficher_erreur(self.erreur)

    def _afficher_erreur(self, message):
        actif = message is not None
        self.bandeau_erreur.setVisible(actif)
        self.lbl_erreur.setText(
            '%s\nCorriger le fichier, puis rouvrir ce panneau.' % message
            if actif else '')
        for w in (self.combo_matiere, self.champ_diametre,
                  self.champ_recherche, self.liste, self.btn_noter):
            w.setEnabled(not actif)

    def _rafraichir_liste(self):
        id_precedent = (self.essai_affiche or {}).get('id')
        mat = self.combo_matiere.currentData() or None
        essais = K.chercher(self.essais, matiere=mat,
                            d=self.champ_diametre.text(),
                            texte=self.champ_recherche.text())
        self.liste.clear()
        ligne = 0 if essais else -1
        for i, e in enumerate(essais):
            it = QListWidgetItem('%s\n%s' % (self._ligne1(e), self._ligne2(e)))
            it.setData(Qt.UserRole, e)
            if not e.get('verdict') and self.palette_active:
                it.setForeground(QColor(self.palette_active['warn_title']))
            self.liste.addItem(it)
            if e.get('id') == id_precedent:
                ligne = i
        if ligne >= 0:
            self.liste.setCurrentRow(ligne)
        else:
            self._afficher_detail(None)

    def _ligne1(self, e):
        z = e.get('z') or 0
        return 'Ø%s · %d dent%s · %s' % (
            _mm(e.get('d')), z, 's' if z != 1 else '', _libelle_matiere(e))

    def _ligne2(self, e):
        bribes = [_date_fr(e.get('date'))]
        if e.get('operation'):
            bribes.append(e['operation'])
        return '%s  ·  %s' % ('  ·  '.join(bribes),
                              e.get('verdict') or '— à compléter —')

    # ------------------------------------------------------------ détail
    def _essai_selectionne(self):
        it = self.liste.currentItem()
        return it.data(Qt.UserRole) if it else None

    def _selection_changee(self, actuel, precedent=None):
        self._afficher_detail(actuel.data(Qt.UserRole) if actuel else None)

    def _afficher_detail(self, e):
        self.essai_affiche = e
        actif = e is not None
        self.btn_completer.setEnabled(actif)
        self.btn_supprimer.setEnabled(actif)
        if not actif:
            self.cadre_photo.definir(None)
            self.lbl_titre_detail.setText('Choisir un essai dans la liste.')
            for lbl in (self.lbl_sous_detail, self.lbl_cotes_detail,
                       self.lbl_verdict_detail, self.lbl_note_detail):
                lbl.setText('')
            self.lbl_copeau.setText('—')
            self.lbl_copeau_note.setText('')
            return

        self.cadre_photo.definir(K.chemin_photo(e, self.dossier))
        self.lbl_titre_detail.setText(self._ligne1(e))
        sous = [_date_fr(e.get('date'))]
        for cle in ('operation', 'travail', 'fraise'):
            if e.get(cle):
                sous.append(e[cle])
        self.lbl_sous_detail.setText('  ·  '.join(sous))
        self.lbl_cotes_detail.setText(
            'Broche %s tr/min  ·  Avance %s mm/min  ·  Ap %s mm  ·  Ae %s mm'
            % (C.fmt(e.get('n') or 0), C.fmt(e.get('vf') or 0),
               _mm(e.get('ap')) or '—', _mm(e.get('ae')) or '—'))
        if e.get('verdict'):
            self.lbl_verdict_detail.setObjectName('')
            self.lbl_verdict_detail.setText('« %s »' % e['verdict'])
        else:
            self.lbl_verdict_detail.setObjectName('texteAvert')
            self.lbl_verdict_detail.setText(
                'Pas encore de verdict — à compléter.')
        self.lbl_verdict_detail.style().unpolish(self.lbl_verdict_detail)
        self.lbl_verdict_detail.style().polish(self.lbl_verdict_detail)
        self.lbl_note_detail.setText(e.get('note') or '')

        fen = self.principale
        comp = K.comparer_theorie(
            e, m_min=fen.f_min.valeur(), m_max=fen.f_max.valeur(),
            plunge=fen.f_plunge.valeur(), vf_max=fen.f_vfmax.valeur())
        if not comp:
            self.lbl_copeau.setText('—')
            self.lbl_copeau_note.setText(
                "Matière ou diamètre absents : pas de comparaison possible.")
        elif comp['rapport_copeau'] is None:
            self.lbl_copeau.setText('—')
            self.lbl_copeau_note.setText(
                "Il manque la broche, l'avance ou le nombre de dents pour "
                "comparer.")
        else:
            pc = comp['rapport_copeau'] * 100
            self.lbl_copeau.setText(C.fmt(pc) + ' %')
            self.lbl_copeau_note.setText('du copeau conseillé — ' + _juge_copeau(pc))

    def _selectionner_id(self, ide):
        for i in range(self.liste.count()):
            if self.liste.item(i).data(Qt.UserRole).get('id') == ide:
                self.liste.setCurrentRow(i)
                return

    # ---------------------------------------------------------- formulaire
    def _noter_essai(self):
        fen = self.principale
        r = getattr(fen, 'dernier', None)
        if not r:
            return
        depart = dict(
            matiere=r['matiere']['id'], d=r['d'], z=r['z'], n=r['n'],
            vf=r['vf'], ae=r['ae'], fraise=fen.e_nom.text().strip(),
            date=datetime.date.today().isoformat())
        dlg = FormulaireEssai(self, 'Noter un essai', self.styleSheet(),
                              dossier=self.dossier, valeurs_defaut=depart)
        if dlg.exec() == QDialog.Accepted:
            self._apres_enregistrement(dlg.resultat)

    def _completer_essai(self, *_ignore):
        e = self._essai_selectionne()
        if not e:
            return
        dlg = FormulaireEssai(self, "Compléter l'essai", self.styleSheet(),
                              dossier=self.dossier, essai_existant=e)
        if dlg.exec() == QDialog.Accepted:
            self._apres_enregistrement(dlg.resultat)

    def _apres_enregistrement(self, essai):
        self._charger()
        if essai:
            self._selectionner_id(essai.get('id'))

    def _supprimer_essai(self):
        e = self._essai_selectionne()
        if not e:
            return
        reponse = QMessageBox.question(
            self, "Carnet d'essais",
            # Pas de parenthèses ici : `_libelle_matiere` en pose déjà autour
            # de la matière, et « (Ø6, douglas (Bois tendre)) » s'emboîtait.
            "Supprimer l'essai du %s — Ø%s, %s ?\nLa photo part avec lui."
            % (_date_fr(e.get('date')), _mm(e.get('d')), _libelle_matiere(e)),
            QMessageBox.Yes | QMessageBox.No, QMessageBox.No)
        if reponse != QMessageBox.Yes:
            return
        try:
            K.supprimer(e['id'], dossier=self.dossier)
        except (ValueError, KeyError) as exc:
            QMessageBox.critical(self, "Carnet d'essais", str(exc))
        self._charger()
