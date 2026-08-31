#!/usr/bin/env python3
# =========================================================================
# coupe_noyau.py — le calcul des vitesses de coupe, sans interface
# © Atelier du Verdier — licence LGPL-2.1-or-later (cf. LICENSE).
# =========================================================================
# Ce module ne connaît ni Qt ni le web : il porte les MATIÈRES et les
# FORMULES, et rien d'autre. Les deux interfaces (l'appli web du site et
# l'appli Qt de l'atelier) doivent en sortir les mêmes nombres — c'est
# testable, et `tests_noyau.py` le teste.
#
# Les valeurs viennent du dossier de remise `design_handoff_vitesses_de_coupe`
# (refonte v16). Elles sont des POINTS DE DÉPART pour fraise carbure sur
# portique amateur, pas des mesures faites sur cette machine-ci.
# =========================================================================

import math

# --- Les matières ---------------------------------------------------------
# vc : vitesse de coupe visée, en m/min.
# k  : copeau par dent et par mm de diamètre — fz conseillé = k × diamètre.
# ap : profondeur de passe conseillée (un texte : c'est une fourchette).
MATIERES = [
    ('Bois', [
        dict(id='bois-tendre', label='Bois tendre', vc=400, k=0.025, ap='3–6 mm',
             note="Pin, sapin, peuplier. Copeau franc : trop lent, ça chauffe et ça brûle."),
        dict(id='bois-dur', label='Bois dur', vc=350, k=0.018, ap='2–4 mm',
             note="Chêne, hêtre, frêne. Sortie propre si l’avance reste soutenue."),
        dict(id='contreplaque', label='Contreplaqué', vc=380, k=0.020, ap='2–5 mm',
             note="Colles abrasives : la fraise s’use vite, préfère une passe franche."),
        dict(id='mdf', label='MDF', vc=420, k=0.022, ap='3–8 mm',
             note="Très abrasif et poussiéreux. Aspiration obligatoire."),
    ]),
    ('Plastiques', [
        dict(id='plexi', label='Plexi', vc=300, k=0.015, ap='1–3 mm',
             note="Fond si ça chauffe : monodent, coupe polie, et surtout pas de "
                  "recoupe du copeau."),
        dict(id='pom', label='POM', vc=350, k=0.018, ap='2–5 mm',
             note="Copeau long : évacuation à l’air comprimé."),
    ]),
    ('Métaux', [
        dict(id='alu', label='Alu', vc=250, k=0.012, ap='0,5–2 mm',
             note="Lubrification indispensable : alcool ou micro-brouillard."),
        dict(id='laiton', label='Laiton', vc=180, k=0.010, ap='0,5–2 mm',
             note="Copeau court, ça part bien. Attention à l’accrochage en entrée."),
        dict(id='acier', label='Acier doux', vc=90, k=0.007, ap='0,2–0,8 mm',
             note="Rigidité avant tout : petites passes, arrosage, et on écoute "
                  "la broche."),
    ]),
]

PAR_ID = {m['id']: m for _famille, items in MATIERES for m in items}


def matiere(mid):
    """La matière d'identifiant `mid`, ou le bois tendre à défaut."""
    return PAR_ID.get(mid, PAR_ID['bois-tendre'])


def num(v, repli):
    """Lit un nombre saisi. Accepte la virgule ET les espaces de groupement.

    Une entrée vide, illisible, nulle ou NÉGATIVE retombe sur `repli` :
    aucune de ces grandeurs — un diamètre, un nombre de dents, une avance —
    ne peut être négative, et il n'y a rien à gagner à propager l'absurde.
    """
    if v is None:
        return repli
    try:
        x = float(str(v).replace(' ', '').replace(' ', '')
                  .replace(' ', '').replace(',', '.'))
    except (TypeError, ValueError):
        return repli
    return x if (math.isfinite(x) and x > 0) else repli


def amincissement(d, ae):
    """Facteur d'amincissement radial du copeau.

    Une fraise n'entre pas droit dans la matière : elle mord en arc. Quand
    elle n'engage qu'une bande étroite sur le côté (ae sous le rayon), le
    copeau réel est plus fin que fz, et elle FROTTE là où l'on croyait
    couper. Le facteur dit de combien relever l'avance pour retrouver le
    copeau visé. Il vaut 1 à la demi-fraise, 1,8 à ae = D/12, et grimpe vite
    en dessous.
    """
    if not (d > 0 and ae > 0) or ae >= d / 2:
        return 1.0
    return 1.0 / math.sqrt(1.0 - (1.0 - (2.0 * ae) / d) ** 2)


def calculer(mat='bois-tendre', d='6', z='2', mode='avance',
             n='', fz='', vf='', ae='',
             m_min='1000', m_max='24000', plunge='35', vf_max='1500'):
    """Résout Vf = N × Z × fz selon le sens demandé.

    Trois grandeurs, une équation : on en saisit deux, la troisième se
    déduit. `mode` dit laquelle est déduite —
      'avance' : broche + copeau -> avance   (le cas courant)
      'broche' : avance + copeau -> broche   (« je veux avancer à 800 »)
      'copeau' : avance + broche -> fz       (« mes réglages valent quoi ? »)

    Les champs `n`, `fz`, `vf` vides signifient « suivre le conseillé ».
    Rend un dictionnaire de valeurs résolues + la liste des avertissements.
    """
    m = matiere(mat)
    d = num(d, 6.0)
    z = max(1, round(num(z, 2)))
    m_min = num(m_min, 1000.0)
    m_max = num(m_max, 24000.0)
    plunge = num(plunge, 35.0)
    vf_max = num(vf_max, 1500.0)

    # Conseillés : la broche découle de la vitesse de coupe de la matière,
    # arrondie au demi-millier — un cadran de variateur ne se règle pas au
    # tour près. Le copeau conseillé est proportionnel au diamètre.
    rec_n = min(m_max, max(m_min, round((m['vc'] * 1000) / (math.pi * d) / 500) * 500))
    rec_fz = round(m['k'] * d * 1000) / 1000

    ae_v = num(ae, 0.0)
    k = amincissement(d, ae_v)

    n_v = num(n, rec_n)
    fz_v = num(fz, rec_fz)
    vf_v = num(vf, 0.0)
    fz_eff = fz_v * k

    if mode == 'avance':
        vf_v = n_v * z * fz_eff
    elif mode == 'broche':
        if not vf_v:
            vf_v = rec_n * z * fz_eff
        n_v = vf_v / (z * fz_eff) if fz_eff else 0.0
    else:                                    # 'copeau'
        if not vf_v:
            vf_v = n_v * z * rec_fz * k
        fz_v = vf_v / (n_v * z * k) if (n_v and k) else 0.0

    vz = vf_v * plunge / 100.0
    vc = math.pi * d * n_v / 1000.0
    fpr = vf_v / n_v if n_v else 0.0

    avertissements = []
    if vf_v > vf_max:
        cible = round(vf_max / (z * fz_eff) / 500) * 500 if fz_eff else 0
        avertissements.append(
            "Vf calculée %s > plafond machine %s mm/min. Viser %s tr/min pour "
            "garder le copeau." % (fmt(vf_v), fmt(vf_max), fmt(cible)))
    if n_v > m_max:
        avertissements.append(
            "Broche %s tr/min au-dessus du max (%s). Prendre une fraise plus "
            "grosse ou accepter un Vc plus bas." % (fmt(n_v), fmt(m_max)))
    elif n_v < m_min:
        avertissements.append(
            "Broche %s tr/min sous le mini (%s). Le couple ne suivra pas."
            % (fmt(n_v), fmt(m_min)))
    if k > 1.6:
        avertissements.append(
            "Passe très fine : copeau aminci ×%s, l’avance a été relevée "
            "d’autant." % str(round(k * 10) / 10).replace('.', ','))

    return dict(matiere=m, d=d, z=z, rec_n=rec_n, rec_fz=rec_fz,
                amincissement=k, ae=ae_v, n=n_v, fz=fz_v, vf=vf_v,
                vz=vz, vc=vc, fpr=fpr, avertissements=avertissements)


def fmt(x, dec=0):
    """Nombre à la française : espace fine pour les milliers, virgule."""
    if x is None or not math.isfinite(x):
        return '—'
    s = ('{:,.%df}' % dec).format(x)
    return s.replace(',', ' ').replace('.', ',')

# =========================================================================
#  La fraise elle-même
# =========================================================================
# Rien de ce qui suit n'entre dans Vf = N x Z x fz : la géométrie ne change
# PAS les vitesses. Elle sert à deux choses, et seulement deux :
#   1. écrire un fichier d'outil FreeCAD (.fctb) qui décrit la vraie fraise
#      plutôt qu'une fraise inventée — FreeCAD s'en sert pour la simulation
#      de collision et la profondeur atteignable ;
#   2. produire des avertissements que la formule ne peut pas donner : une
#      fraise qui ne plonge pas, une descendante qui n'évacue rien, une
#      hauteur de coupe plus courte que la passe conseillée.

# Les formes que FreeCAD sait dessiner, et le paramètre propre à chacune.
FORMES = [
    dict(id='plat',     label='Plat',    shape='endmill.fcstd',  type='Endmill',  extra=None),
    dict(id='boule',    label='Boule',   shape='ballend.fcstd',  type='Ballend',  extra=None),
    dict(id='torique',  label='Torique', shape='bullnose.fcstd', type='Bullnose',
         extra=('rayon', 'Rayon de coin', 'mm', 'CornerRadius')),
    dict(id='vbit',     label='V',       shape='v-bit.fcstd',    type='V-bit',
         extra=('angle', 'Angle de pointe', '°', 'CuttingEdgeAngle')),
]
FORME_PAR_ID = {f['id']: f for f in FORMES}

# Le sens de l'hélice. Il ne change aucun chiffre, mais il commande la
# façon dont le copeau sort — donc la profondeur de passe raisonnable.
HELICES = [
    dict(id='montante',    label='Montante',
         note="Les copeaux sortent vers le haut : rainures profondes possibles, "
              "mais la face du dessus s'écaille."),
    dict(id='descendante', label='Descendante',
         note="Belle face du dessus, mais les copeaux sont tassés dans la "
              "rainure : réduire la profondeur de passe, ça chauffe vite.",
         alerte="Fraise descendante : les copeaux ne s’évacuent pas vers le "
                "haut. Passes moins profondes, et surveiller l’échauffement."),
    dict(id='compression', label='Compression',
         note="Propre des deux côtés, mais il lui faut une profondeur "
              "suffisante pour que la partie basse morde.",
         alerte="Fraise de compression : sous une certaine profondeur, la "
                "partie basse ne travaille pas et l’intérêt disparaît."),
    dict(id='droite',      label='Droite',
         note="Pas d'hélice : effort axial faible, évacuation médiocre."),
]
HELICE_PAR_ID = {h['id']: h for h in HELICES}


def geometrie(d, forme='plat', hauteur_coupe=None, longueur=None,
              queue=None, rayon=None, angle=None):
    """Complète la géométrie d'une fraise, en déduisant ce qui manque.

    Les valeurs déduites sont des ordres de grandeur d'usage — hauteur de
    coupe 3 x Ø, longueur 8 x Ø, queue au diamètre de coupe. Elles ne valent
    que tant que personne n'a mesuré la vraie fraise, et c'est justement ce
    que les champs permettent de corriger.
    """
    d = num(d, 6.0)
    f = FORME_PAR_ID.get(forme, FORME_PAR_ID['plat'])
    g = dict(
        forme=f,
        diametre=d,
        hauteur_coupe=num(hauteur_coupe, round(d * 3, 2)),
        longueur=num(longueur, round(d * 8, 2)),
        queue=num(queue, d),
        deduit=[],
    )
    for cle, valeur in (('hauteur_coupe', hauteur_coupe), ('longueur', longueur),
                        ('queue', queue)):
        if not num(valeur, 0):
            g['deduit'].append(cle)
    if f['id'] == 'torique':
        g['rayon'] = num(rayon, round(d / 6, 2))
    if f['id'] == 'vbit':
        g['angle'] = num(angle, 90.0)
    # Une longueur totale plus courte que la partie coupante n'a pas de sens.
    if g['longueur'] < g['hauteur_coupe']:
        g['longueur'] = round(g['hauteur_coupe'] * 1.5, 2)
    return g


def fichier_outil(nom, g, z, fz, helice='montante', plongeant=True):
    """Le .fctb que FreeCAD attend, décrivant la fraise telle qu'elle est.

    `shape-type` compte autant que `shape` : c'est lui que le Gestionnaire
    de bibliothèque lit pour classer l'outil et choisir son icône.
    """
    p = {
        'Diameter': '%g mm' % g['diametre'],
        'Flutes': max(1, int(round(num(z, 2)))),
        'Chipload': '%g mm' % num(fz, 0),
        'CuttingEdgeHeight': '%g mm' % g['hauteur_coupe'],
        'Length': '%g mm' % g['longueur'],
        'ShankDiameter': '%g mm' % g['queue'],
        'Material': 'Carbide',
    }
    if 'rayon' in g:
        p['CornerRadius'] = '%g mm' % g['rayon']
    if 'angle' in g:
        p['CuttingEdgeAngle'] = '%g °' % g['angle']
        p['TipDiameter'] = '0.1 mm'
    return {
        'version': 2,
        'name': nom,
        'shape': g['forme']['shape'],
        'shape-type': g['forme']['type'],
        'parameter': p,
        # Ce que FreeCAD ne sait pas ranger, mais qu'on ne veut pas perdre.
        'attribute': {'helice': helice, 'plongeant': bool(plongeant)},
    }


def avertissements_fraise(g, helice='montante', plongeant=True, ap_texte=''):
    """Ce que la géométrie impose et que la formule ne dit pas."""
    liste = []
    h = HELICE_PAR_ID.get(helice)
    if h and h.get('alerte'):
        liste.append(h['alerte'])
    if not plongeant:
        liste.append("Bout non plongeant : entrer en rampe ou en hélice, "
                     "jamais droit dans la matière.")
    # La passe conseillée tient-elle dans la partie coupante ?
    profondeurs = [float(x.replace(',', '.'))
                   for x in __import__('re').findall(r'[\d,]+', ap_texte or '')]
    if profondeurs and g['hauteur_coupe'] < max(profondeurs):
        liste.append("La fraise ne coupe que sur %g mm, moins que la passe "
                     "conseillée : plusieurs passes, ou une fraise plus longue."
                     % g['hauteur_coupe'])
    return liste

