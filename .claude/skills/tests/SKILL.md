---
name: tests
description: >-
  Vérifier vitesses-coupe : les quatre suites (noyau, carnet, bibliothèque FreeCAD,
  interface offscreen) puis la comparaison au jumeau JavaScript du site sous node,
  le tout sur des dossiers jetables, sans jamais toucher la vraie configuration ni le
  carnet d'essais. À charger après toute modification de ce dépôt, et quand l'appli
  web du site (site/appli/coupe) est retouchée.
---

# Vérifier vitesses-coupe

## 1. Les cinq contrôles, verdict par code de sortie

```bash
python3 -c "import ast; [ast.parse(open(f).read()) for f in ('coupe_noyau.py','vitesses_coupe.py','carnet_noyau.py','carnet_ui.py','freecad_biblio.py')]"
for t in tests_noyau tests_carnet tests_biblio tests_interface tests_jumeau_web; do python3 $t.py >/dev/null; echo "$t : $?"; done
```

- `tests_noyau.py` : les formules, contre les captures du dossier de remise
  (Vf 6 300, broche 21 000, 0,30 mm/tr). Un test qui reprend la formule qu'il
  vérifie ne vérifie rien.
- `tests_carnet.py` : le carnet, dans un dossier jetable ; un carnet abîmé n'est
  jamais écrasé.
- `tests_biblio.py` : l'aller-retour `.fctb`/`.fctl`, sur ce que FreeCAD 1.1.3
  écrit vraiment (virgules françaises, `attribute` vidé) ; pas d'écrasement
  d'un autre outil.
- `tests_interface.py` : les widgets manipulés hors écran. C'est lui qui aurait
  attrapé le défaut du 03/09/2026 (changer le diamètre ne changeait plus rien).
- `tests_jumeau_web.py` : rejoue le `calculer` de
  `~/Projets/site/Site_AtelierDuVerdier/site/appli/coupe/index.html` sous
  `node` sur 8 505 combinaisons et exige **zéro écart** de nombre et de texte
  avec `coupe_noyau.py`. Ignoré (sortie 0 avec message) si node ou le site
  manquent.

## 2. Jamais la vraie configuration

`~/.config/vitesses-coupe/reglages.json` (bibliothèque d'outils, limites
machine), `vitesses-freecad.json` (vitesses liées aux `.fctb`) et
`~/Projets/machine/carnet-essais/` sont des relevés d'établi. Chaque suite
repointe `V.FICHIER_CONF`, `FB.FICHIER_VITESSES`, `K.DOSSIER_DEFAUT` vers un
dossier temporaire **avant** la première fenêtre, et vérifie leurs empreintes
en dernier contrôle. Un nouveau test fait pareil.

## 3. L'état saisi, distinct de l'affiché

Les champs broche, copeau et avance ont un `saisi` (ce que l'utilisateur a tapé)
et un affichage (le conseillé, posé par l'appli quand rien n'est saisi). Le
calcul lit `saisi`, jamais le texte du widget. C'est la règle de l'appli web
(`S.n`), et la casser redonne le bug du 03/09.

## 4. Si l'appli web change

Même table de matières, mêmes formules, mêmes textes d'avertissement des deux
côtés. Après une retouche de `index.html` : relancer `tests_jumeau_web.py`,
puis bumper `CACHE` dans `sw.js` et publier (skill `publier` du site).

## 5. Puis regarder

`python3 vitesses_coupe.py`, changer le diamètre, le résultat doit bouger sans
toucher au ↻ ; ouvrir le carnet ; basculer le thème (`Ctrl+J`). La capture
offscreen (skill `capture-qt`) pour les deux thèmes si la feuille de style a bougé.
