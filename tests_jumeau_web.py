#!/usr/bin/env python3
# =========================================================================
# tests_jumeau_web.py — l'appli web du site calcule-t-elle comme le noyau ?
# © Atelier du Verdier — licence LGPL-2.1-or-later (cf. LICENSE).
# =========================================================================
# Le README promet « le même calcul » entre cette appli et celle servie sur
# atelierduverdier.fr/coupe/, qui porte une traduction JavaScript de
# `coupe_noyau.py`. Une promesse se vérifie : on charge le script de la page
# sous `node` avec un DOM factice, on lui rejoue des milliers de combinaisons
# (matières × diamètres × dents × sens × largeurs ae × saisies) et on exige
# ZÉRO écart — de nombre comme de texte d'avertissement. Le 03/09/2026, ce
# rejeu a trouvé 2 230 textes différents sur 8 505 cas : la broche « à viser »
# était arrondie au plus proche d'un côté et vers le bas de l'autre.
#
# Ignoré (sortie 0, avec un mot) si `node` ou le dépôt du site manquent :
# c'est un contrôle d'accord entre deux dépôts, pas une dépendance du noyau.
#
#   python3 tests_jumeau_web.py
# =========================================================================

import json
import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

import coupe_noyau as C

PAGE = (Path.home() / 'Projets' / 'site' / 'Site_AtelierDuVerdier'
        / 'site' / 'appli' / 'coupe' / 'index.html')
# Pour saboter le filet : JUMEAU_PAGE=/tmp/copie_abimee.html python3 tests_jumeau_web.py
PAGE = Path(os.environ.get('JUMEAU_PAGE') or PAGE)

HARNAIS_JS = r'''
const fs = require('fs');
const bidon = new Proxy(function(){}, {
  get: (t, p) => p === Symbol.toPrimitive ? () => '' : bidon,
  apply: () => bidon, set: () => true });
global.window = global; global.document = bidon; global.navigator = bidon;
global.location = bidon; global.addEventListener = () => {};
global.requestAnimationFrame = () => {}; global.setTimeout = () => {};
global.matchMedia = () => ({ matches: false, addEventListener(){} });
global.localStorage = { getItem: () => null, setItem(){}, removeItem(){} };
const src = fs.readFileSync(process.argv[2], 'utf8');
new Function(src + '\n;global.__calculer = calculer; global.__S = S;')();
const cas = JSON.parse(fs.readFileSync(process.argv[3], 'utf8'));
const proche = (a, b) => Math.abs(a - b) <= 1e-6 * Math.max(1, Math.abs(a), Math.abs(b));
const paires = [['n','n'],['fz','fz'],['vf','vf'],['vz','vz'],['vc','vc'],
                ['fpr','fpr'],['recN','rec_n'],['recFz','rec_fz'],['thinning','k']];
let ecarts = [];
for (const c of cas) {
  Object.assign(__S, { mat: c.mat, d: c.d, z: c.z, mode: c.mode, ae: c.ae, n: c.n,
    fz: c.fz, vf: c.vf, vfMax: c.vfMax, mMin: '1000', mMax: '24000', plunge: '35' });
  const r = __calculer(), a = c.attendu, diff = [];
  for (const [js, py] of paires) if (!proche(r[js], a[py])) diff.push(`${js}: js=${r[js]} py=${a[py]}`);
  if (r.warns.length !== a.avert.length) diff.push(`avertissements: js=${r.warns.length} py=${a.avert.length}`);
  else r.warns.forEach((w, i) => { if (w !== a.avert[i]) diff.push(`texte: js=«${w}» py=«${a.avert[i]}»`); });
  if (diff.length) ecarts.push({ cas: c, diff });
}
console.log(JSON.stringify({ total: cas.length, ecarts: ecarts.slice(0, 5), nb_ecarts: ecarts.length }));
'''


def script_de_la_page(html):
    """Le premier bloc <script> de la page : celui de l'appli."""
    debut = html.index('<script>') + len('<script>')
    fin = html.index('</script>', debut)
    return html[debut:fin]


def cas_de_reference():
    cas = []
    for mat in C.PAR_ID:
        for d in ('1', '2', '3.175', '6', '6,35', '8', '12'):
            for z in ('1', '2', '3'):
                for mode in ('avance', 'broche', 'copeau'):
                    for ae in ('', '0,3', '1'):
                        for n, fz, vf in (('', '', ''), ('18000', '', ''), ('', '0,05', ''),
                                          ('', '', '800'), ('12000', '0,1', '900')):
                            cas.append(dict(mat=mat, d=d, z=z, mode=mode, ae=ae,
                                            n=n, fz=fz, vf=vf, vfMax='1500'))
    for c in cas:
        r = C.calculer(c['mat'], c['d'], c['z'], c['mode'], c['n'], c['fz'],
                       c['vf'], c['ae'], vf_max=c['vfMax'])
        c['attendu'] = dict(n=r['n'], fz=r['fz'], vf=r['vf'], vz=r['vz'], vc=r['vc'],
                            fpr=r['fpr'], rec_n=r['rec_n'], rec_fz=r['rec_fz'],
                            k=r['amincissement'], avert=r['avertissements'])
    return cas


def main():
    node = shutil.which('node')
    if not node:
        print("node absent : comparaison au jumeau web ignorée.")
        return 0
    if not PAGE.is_file():
        print("Dépôt du site absent (%s) : comparaison au jumeau web ignorée." % PAGE)
        return 0
    bac = Path(tempfile.mkdtemp(prefix='jumeau-web-'))
    (bac / 'appli.js').write_text(script_de_la_page(PAGE.read_text(encoding='utf-8')),
                                  encoding='utf-8')
    (bac / 'harnais.js').write_text(HARNAIS_JS, encoding='utf-8')
    cas = cas_de_reference()
    (bac / 'cas.json').write_text(json.dumps(cas), encoding='utf-8')
    r = subprocess.run([node, str(bac / 'harnais.js'), str(bac / 'appli.js'),
                        str(bac / 'cas.json')], capture_output=True, text=True)
    if r.returncode != 0:
        print("ÉCHEC  le script de la page ne se charge pas sous node :\n" + r.stderr[-800:])
        return 1
    bilan = json.loads(r.stdout.strip().splitlines()[-1])
    print("%d combinaisons rejouées dans l'appli web." % bilan['total'])
    if bilan['nb_ecarts']:
        print("ÉCHEC  %d écart(s) entre l'appli web et coupe_noyau.py, par exemple :"
              % bilan['nb_ecarts'])
        for e in bilan['ecarts']:
            c = e['cas']
            print("  %s Ø%s Z%s %s ae=%r n=%r fz=%r vf=%r" % (
                c['mat'], c['d'], c['z'], c['mode'], c['ae'], c['n'], c['fz'], c['vf']))
            for d in e['diff']:
                print("     " + d)
        return 1
    print("  OK     zéro écart de nombre, zéro écart de texte.")
    print("\nTout passe.")
    return 0


if __name__ == '__main__':
    sys.exit(main())
