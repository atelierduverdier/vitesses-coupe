# Vitesses de coupe — l'appli de bureau

Calculateur d'avances et de vitesses pour le fraisage CNC, en PySide6.
C'est la **même appli** que celle servie sur
<https://atelierduverdier.fr/coupe/>, avec la même mise en page et — surtout —
**le même calcul** : les deux appellent `coupe_noyau.py`.

```bash
python3 vitesses_coupe.py
```

## Ce qu'elle fait

On choisit une matière (neuf, du sapin à l'acier doux), on donne le diamètre
de fraise et le nombre de dents, et l'appli déduit **au choix** :

| Ce qu'elle calcule | Ce qu'on saisit | La question posée |
|---|---|---|
| **L'avance** | broche + copeau | « Ma broche tourne à 21 000, à quelle vitesse avancer ? » |
| **La broche** | avance + copeau | « Je veux avancer à 800 mm/min, à combien régler la broche ? » |
| **Le copeau** | avance + broche | « Voilà ce que j'utilise — ça vaut quelque chose ? » |

Le troisième sens est un **diagnostic** : l'aide sous le champ dit le copeau
obtenu en pourcentage du conseillé. 21 000 tr/min à 800 mm/min avec une fraise
de 6 à deux dents, c'est 13 % du copeau utile — la fraise frotte au lieu de
couper, et c'est ce qui brûle le bois.

Avec, en plus : la **largeur de coupe** (ae) qui corrige l'amincissement du
copeau en reprise de contour, les **réglages machine** repliés, une
**bibliothèque d'outils**, l'export **`.fctb`** pour FreeCAD, et un thème
**jour / nuit** (jour par défaut, `Ctrl+J`).

## Les fichiers

| | |
|---|---|
| `coupe_noyau.py` | les matières et les formules. Ni Qt ni web — la couche qu'on teste. |
| `vitesses_coupe.py` | l'interface PySide6. |
| `tests_noyau.py` | 61 contrôles sur le calcul : `python3 tests_noyau.py` |
| `tests_interface.py` | l'interface fait-elle ce que le noyau calcule ? Sans écran, sur une configuration jetable : `python3 tests_interface.py` |
| `tests_jumeau_web.py` | l'appli web du site calcule-t-elle pareil ? Son JavaScript rejoué sous `node` sur 8 505 combinaisons, zéro écart exigé : `python3 tests_jumeau_web.py` |
| `carnet_noyau.py` | **le carnet d'essais** : la théorie calcule, le carnet retient ce que la matière a répondu. Ni Qt ni web. |
| `carnet_ui.py` | l'interface du carnet — consulter, noter, compléter, supprimer. PySide6, greffée sur `vitesses_coupe.py`. |
| `tests_carnet.py` | les contrôles du carnet : `python3 tests_carnet.py` |
| `importer_outil_coupe.FCMacro` | **le bouton de l'atelier CAM** : crée la fraise, son Tool Controller et pose les vitesses |
| `icone_outil_coupe.svg` | l'icône de ce bouton |
| `macro_tool_controller.py` | macro plus ancienne : remplit un Tool Controller **existant** depuis le fichier d'« Export JSON… » |
| `freecad_biblio.py` | lit et écrit les bibliothèques d'outils de FreeCAD, **sans dépendre de FreeCAD** |
| `tests_biblio.py` | les contrôles de cet aller-retour, sur ce que FreeCAD 1.1.3 écrit vraiment : `python3 tests_biblio.py` |

**Le noyau est partagé avec l'appli web du site**, qui en porte une
traduction JavaScript ligne pour ligne. Les valeurs de référence des tests ne
sortent pas du code : elles viennent des captures du dossier de remise
(`design_handoff_vitesses_de_coupe`), qui affichent Vf 6 300, broche 21 000,
Vz 2 205, Vc 396 et 0,30 mm/tr pour du bois tendre en Ø6 à deux dents. Un test
qui reprend la formule qu'il vérifie ne vérifie rien.

## Vers FreeCAD

Un fichier d'outil `.fctb` décrit la **fraise** — diamètre, dents, longueurs — et
ne peut pas porter de vitesses : celles-ci appartiennent au **Tool Controller**
du Job, qui naît donc à zéro. Deux façons de le remplir :

* **à la main** — l'appli affiche les cinq valeurs à recopier ;
* **avec le bouton de l'atelier CAM** — `importer_outil_coupe.FCMacro`. Un clic,
  on choisit une fraise **dans sa bibliothèque**, et elle arrive dans le Job avec
  son Tool Controller et ses vitesses. C'est la voie normale.

  > Le bouton ne CRÉE pas d'outil, il pioche dans la bibliothèque. C'est l'appli
  > qui y écrit, par « ↑ Écrire dans FreeCAD… ». Faire les deux mènerait à la
  > **même fraise en double** — celle de l'appli, complète, et celle de la macro,
  > à la géométrie déduite. C'est arrivé le 31/08 : six entrées pour cinq fraises.
* **avec l'ancienne macro** — `macro_tool_controller.py`, quand le contrôleur
  existe déjà et qu'on veut seulement le remplir.

### Poser le bouton dans l'atelier CAM (une fois)

1. copier `importer_outil_coupe.FCMacro` **et** `icone_outil_coupe.svg` dans
   le dossier des macros. **Attention, il est VERSIONNÉ** : FreeCAD 1.1 lit
   `~/.local/share/FreeCAD/v1-1/Macro`, et un `~/.local/share/FreeCAD/Macro`
   sans numéro de version peut exister à côté sans jamais être lu. En cas de
   doute, la réponse vient de FreeCAD lui-même :

   ```python
   FreeCAD.getUserMacroDir(True)
   ```
2. **Outils → Personnaliser… → onglet Macros** : choisir la macro, lui donner
   un texte de menu (« Importer un outil de coupe »), désigner l'icône, puis
   **Ajouter** ;
3. **onglet Barres d'outils**, atelier **CAM**, créer ou choisir une barre et y
   déplacer la commande avec la flèche →.

Le bouton n'apparaît alors que dans l'atelier CAM.

Le bouton n'a besoin d'**aucun fichier exporté** : il lit la bibliothèque de
FreeCAD et les vitesses que l'appli a retenues à côté
(`~/.config/vitesses-coupe/vitesses-freecad.json`). **Export JSON…**, sous la
bibliothèque, ne sert plus qu'à l'ancienne macro.

> **Deux pièges que le bouton évite**, mesurés sur FreeCAD 1.1.3.
>
> **Les unités.** `HorizFeed`, `VertFeed`, `HorizRapid` et `VertRapid` sont
> comptées en **mm/s** alors que l'interface affiche des mm/min. Écrire
> `tc.HorizFeed = 6300` ne lève aucune erreur et donne **378 000 mm/min** —
> soixante fois trop. Seule la forme `tc.HorizFeed = "6300 mm/min"` est juste.
>
> **Les rapides n'appartiennent pas à l'outil.** Elles vivent dans le
> `SetupSheet` du Job, qui les réimpose au Tool Controller à chaque recalcul :
> posées sur le contrôleur elles retombent à zéro, avant comme après l'ajout au
> Job. C'est cohérent — un rapide dépend de la machine, pas de la fraise — mais
> rien ne le signale et la valeur disparaît en silence.

Les deux **rapides** ne sortent pas du calcul : ce sont des vitesses de
transport, propres à la machine. Elles se règlent dans le panneau « Machine »
et se lisent dans la configuration LinuxCNC (`MAX_VELOCITY` de chaque axe, en
mm/s — à multiplier par 60).

## L'aller-retour avec les bibliothèques FreeCAD

Deux boutons sous la bibliothèque :

* **↓ Lire FreeCAD…** — reprendre un outil d'une bibliothèque existante. La
  géométrie vient de FreeCAD ; les vitesses reviennent aussi **si l'appli les
  connaît**, sinon elle les calcule pour la matière choisie.
* **↑ Écrire dans FreeCAD…** — poser l'outil dans une bibliothèque. Il apparaît
  alors dans le Gestionnaire de bibliothèque, et le Job peut s'en servir. Si
  aucun outil n'est choisi dans la liste, c'est celui **à l'écran** qui est
  écrit, et il est enregistré au passage.

### Le cycle, pour une fraise neuve

| | |
|---|---|
| 1 | matière, diamètre, dents — et le détail de la fraise si on l'a |
| 2 | **↑ Écrire dans FreeCAD…** : la fraise et ses vitesses sont liées |
| 3 | dans FreeCAD, le bouton CAM : le Job reçoit la fraise **et** ses cinq valeurs |

L'étape 3 s'appuie sur la 2 : c'est en écrivant dans FreeCAD que les vitesses
sont retenues, et c'est là que le bouton va les chercher. Si deux outils
différents se disputent le même nom de fichier — « Essai · Ø6,35 » et
« Essai - Ø6.35 » y arrivent tous deux — le second est numéroté (`_2`) plutôt
que d'écraser le premier ; seul un outil du **même nom** réécrit son fichier.

> **Pourquoi les vitesses vivent à côté.** Un `.fctb` a bien un champ libre, et
> l'on pourrait croire qu'il suffit d'y ranger broche et avance. Mesuré sur
> FreeCAD 1.1.3 : **il le vide** dès qu'il réécrit l'outil, sans message. Les
> vitesses sont donc gardées par l'appli dans
> `~/.config/vitesses-coupe/vitesses-freecad.json`, rattachées au **nom du
> fichier** `.fctb` — le seul point fixe qui survive à un aller-retour.

> **Le dossier de FreeCAD est versionné**, et plusieurs versions cohabitent
> presque toujours (`v1-1`, `v1-2`, `v26-3`…). Deviner lequel est le bon est un
> piège : trier par date de modification désignait ici la version de
> développement alors que la machine tourne sur la stable. L'appli fait donc
> choisir, en montrant combien d'outils chacun contient, et retient la réponse.

### Le jour où vous changerez de version de FreeCAD

Le dossier de données de FreeCAD est **versionné** : `v1-1`, `v1-2`, `v26-3`…
Une nouvelle version majeure repart d'un dossier **neuf**, et vos fraises n'y
sont pas. Les vitesses, elles, restent — elles vivent dans
`~/.config/vitesses-coupe/`, hors de FreeCAD.

Rien n'est perdu, mais rien ne suit tout seul. Pour emporter la bibliothèque :

```bash
# adapter les deux versions
cp -r ~/.local/share/FreeCAD/v1-1/CamAssets/Tools/Bit/*.fctb \
      ~/.local/share/FreeCAD/v1-2/CamAssets/Tools/Bit/
cp    ~/.local/share/FreeCAD/v1-1/CamAssets/Tools/Library/*.fctl \
      ~/.local/share/FreeCAD/v1-2/CamAssets/Tools/Library/
```

Le lien avec les vitesses tient au **nom du fichier** `.fctb` : tant qu'il ne
change pas, elles reviennent. Renommer un outil dans FreeCAD (son libellé) ne
casse rien ; renommer son fichier, si.

## Raccourcis

| | |
|---|---|
| `Ctrl+J` | jour / nuit |
| `Ctrl+S` | enregistrer l'outil courant |
| `Ctrl+Q` | quitter |

## Où vivent les réglages

`~/.config/vitesses-coupe/reglages.json` — le thème, les limites machine et la
bibliothèque d'outils. Pas dans le dossier du programme : celui-ci est un
dépôt qu'on met à jour.

## Les valeurs sont des points de départ

Elles viennent de tables constructeur pour fraise carbure sur portique
amateur, **pas de mesures faites sur cette machine**. Le vrai juge est le
copeau : s'il sort en filaments souples et que le bois ne noircit pas, c'est
bon ; s'il sort en poussière et que ça fume, la fraise frotte.

Les champs broche et copeau affichent le **conseillé** tant qu'on n'y a rien
tapé, et le suivent quand le diamètre, les dents ou la matière changent. Une
valeur **tapée**, elle, tient jusqu'au ↻ ou jusqu'à un changement de matière
ou de sens de calcul — c'est la règle de l'appli web, et l'appli de bureau
l'a longtemps manquée : elle relisait le conseillé posé comme une saisie, et
changer le diamètre ne changeait plus rien (corrigé le 03/09/2026).

Et l'avance calculée n'est pas toujours tenable : une PrintNC décroche
au-delà de 600 à 800 mm/min dans les courbes. C'est à ça que sert le champ
**Avance max** — l'appli avertit alors et propose la broche qui garde le
copeau sous ce plafond.

## Le carnet d'essais

La section précédente le dit : les valeurs sont des points de départ, le vrai
juge est le copeau. Le carnet est l'endroit où ce jugement s'écrit — le
pendant fraiseuse du nuancier laser.

Un essai retient la matière telle qu'elle était (« chêne de récup »), la
fraise, les vitesses réellement tenues, une photo du résultat et un **verdict
court** (« propre », « ça brûle »). Le bouton **« Carnet d'essais »**, en
haut de la fenêtre, ouvre le carnet dans un panneau à part — une fenêtre
annexe, non modale : elle reste ouverte pendant qu'on retouche le
calculateur juste à côté, et c'est même l'intérêt.

**Avant un nouveau travail, on consulte.** Le panneau s'ouvre déjà filtré
sur la matière et le Ø du calculateur — il sait déjà ce qu'on s'apprête à
fraiser. La liste vient de `chercher()` : les essais de la matière, du Ø le
plus proche au plus lointain puis du plus récent au plus ancien ; un champ
cherche aussi en texte libre (essence, verdict, travail…), sans se soucier
des accents. Un essai sans verdict se voit d'un coup d'œil dans la liste
(teinté comme un avertissement) : c'est un essai à compléter. Choisir un
essai affiche sa photo, ses cotes et le **rapport de copeau** rendu par
`comparer_theorie()` — 13 %, c'est la fraise qui frottait.

**Après le travail, on note.** Le bouton « + Noter un essai » préremplit le
formulaire depuis l'état courant du calculateur (matière, Ø, dents, broche,
avance) ; il ne reste qu'à ajouter l'essence, l'opération, le verdict et,
si on l'a, une photo. « Compléter… » rouvre le même formulaire sur un essai
déjà noté — le verdict et la photo arrivent souvent après coup — et
« Supprimer » retire un essai (avec confirmation, photo comprise).

Le carnet vit **hors du dépôt**, avec les affaires de la machine :
`~/Projets/machine/carnet-essais/` — un `carnet.json` lisible, qui n'est
jamais écrasé s'il est abîmé (le panneau le dit, plutôt que de repartir sur
une liste vide), et les photos à côté, nommées comme les essais.

## Licence

**LGPL-2.1-or-later**, comme [LaserAtelier](https://github.com/atelierduverdier/LaserAtelier).
Voir [`LICENSE`](LICENSE).

© Atelier du Verdier
