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
| `tests_noyau.py` | 38 contrôles sur le calcul : `python3 tests_noyau.py` |

**Le noyau est partagé avec l'appli web du site**, qui en porte une
traduction JavaScript ligne pour ligne. Les valeurs de référence des tests ne
sortent pas du code : elles viennent des captures du dossier de remise
(`design_handoff_vitesses_de_coupe`), qui affichent Vf 6 300, broche 21 000,
Vz 2 205, Vc 396 et 0,30 mm/tr pour du bois tendre en Ø6 à deux dents. Un test
qui reprend la formule qu'il vérifie ne vérifie rien.

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

Et l'avance calculée n'est pas toujours tenable : une PrintNC décroche
au-delà de 600 à 800 mm/min dans les courbes. C'est à ça que sert le champ
**Avance max** — l'appli avertit alors et propose la broche qui garde le
copeau sous ce plafond.

## Licence

**LGPL-2.1-or-later**, comme [LaserAtelier](https://github.com/atelierduverdier/LaserAtelier).
Voir [`LICENSE`](LICENSE).

© Atelier du Verdier
