"""
Tests statistiques en Python pur (aucune dépendance externe).

Le sandbox n'a pas d'accès réseau : scipy/numpy sont indisponibles. Ce module
réimplémente les fonctions nécessaires à l'analyse :

  - Fonctions spéciales : log-gamma, bêta incomplète, gamma incomplète
  - ANOVA à un facteur (F de Fisher + p-value)
  - Test t de Welch (variances inégales)
  - Chi-carré d'indépendance + V de Cramér
  - Corrélation de Spearman
  - Cohen's d, intervalles de confiance à 95 %
  - Shrinkage bayésien empirique (James-Stein)

Les algorithmes de fonctions spéciales suivent les développements classiques
en fractions continues (cf. Numerical Recipes), avec une précision de ~1e-10,
largement suffisante pour des p-values.
"""

from __future__ import annotations

import math
from typing import Sequence

ALPHA = 0.05

# ---------------------------------------------------------------------------
# 1. Fonctions spéciales
# ---------------------------------------------------------------------------

_LANCZOS = [
    76.18009172947146,
    -86.50532032941677,
    24.01409824083091,
    -1.231739572450155,
    0.1208650973866179e-2,
    -0.5395239384953e-5,
]


def gammln(x: float) -> float:
    """Logarithme naturel de la fonction gamma (approximation de Lanczos)."""
    y = x
    tmp = x + 5.5
    tmp -= (x + 0.5) * math.log(tmp)
    ser = 1.000000000190015
    for coef in _LANCZOS:
        y += 1.0
        ser += coef / y
    return -tmp + math.log(2.5066282746310005 * ser / x)


def _betacf(a: float, b: float, x: float) -> float:
    """Fraction continue pour la fonction bêta incomplète (Lentz modifié)."""
    MAXIT, EPS, FPMIN = 300, 3.0e-16, 1.0e-300

    qab, qap, qam = a + b, a + 1.0, a - 1.0
    c = 1.0
    d = 1.0 - qab * x / qap
    if abs(d) < FPMIN:
        d = FPMIN
    d = 1.0 / d
    h = d

    for m in range(1, MAXIT + 1):
        m2 = 2 * m
        # Pas pair
        aa = m * (b - m) * x / ((qam + m2) * (a + m2))
        d = 1.0 + aa * d
        if abs(d) < FPMIN:
            d = FPMIN
        c = 1.0 + aa / c
        if abs(c) < FPMIN:
            c = FPMIN
        d = 1.0 / d
        h *= d * c
        # Pas impair
        aa = -(a + m) * (qab + m) * x / ((a + m2) * (qap + m2))
        d = 1.0 + aa * d
        if abs(d) < FPMIN:
            d = FPMIN
        c = 1.0 + aa / c
        if abs(c) < FPMIN:
            c = FPMIN
        d = 1.0 / d
        delta = d * c
        h *= delta
        if abs(delta - 1.0) < EPS:
            break
    return h


def betai(a: float, b: float, x: float) -> float:
    """Fonction bêta incomplète régularisée I_x(a, b)."""
    if x <= 0.0:
        return 0.0
    if x >= 1.0:
        return 1.0
    bt = math.exp(
        gammln(a + b) - gammln(a) - gammln(b) + a * math.log(x) + b * math.log(1.0 - x)
    )
    if x < (a + 1.0) / (a + b + 2.0):
        return bt * _betacf(a, b, x) / a
    return 1.0 - bt * _betacf(b, a, 1.0 - x) / b


def _gser(a: float, x: float) -> float:
    """Gamma incomplète P(a,x) par développement en série."""
    EPS, ITMAX = 3.0e-16, 1000
    gln = gammln(a)
    if x <= 0.0:
        return 0.0
    ap, somme, delta = a, 1.0 / a, 1.0 / a
    for _ in range(ITMAX):
        ap += 1.0
        delta *= x / ap
        somme += delta
        if abs(delta) < abs(somme) * EPS:
            break
    return somme * math.exp(-x + a * math.log(x) - gln)


def _gcf(a: float, x: float) -> float:
    """Gamma incomplète complémentaire Q(a,x) par fraction continue."""
    EPS, FPMIN, ITMAX = 3.0e-16, 1.0e-300, 1000
    gln = gammln(a)
    b = x + 1.0 - a
    c = 1.0 / FPMIN
    d = 1.0 / b
    h = d
    for i in range(1, ITMAX + 1):
        an = -i * (i - a)
        b += 2.0
        d = an * d + b
        if abs(d) < FPMIN:
            d = FPMIN
        c = b + an / c
        if abs(c) < FPMIN:
            c = FPMIN
        d = 1.0 / d
        delta = d * c
        h *= delta
        if abs(delta - 1.0) < EPS:
            break
    return math.exp(-x + a * math.log(x) - gln) * h


def gammq(a: float, x: float) -> float:
    """Fonction gamma incomplète complémentaire Q(a,x) = 1 - P(a,x)."""
    if x < 0.0 or a <= 0.0:
        raise ValueError("gammq : arguments invalides")
    if x < a + 1.0:
        return 1.0 - _gser(a, x)
    return _gcf(a, x)


# ---------------------------------------------------------------------------
# 2. Lois de probabilité : p-values
# ---------------------------------------------------------------------------


def p_value_f(f_stat: float, df1: int, df2: int) -> float:
    """P(F > f_stat) pour une loi de Fisher à (df1, df2) degrés de liberté."""
    if f_stat <= 0 or df1 <= 0 or df2 <= 0:
        return 1.0
    return betai(df2 / 2.0, df1 / 2.0, df2 / (df2 + df1 * f_stat))


def p_value_t(t_stat: float, df: float) -> float:
    """P-value bilatérale pour un t de Student."""
    if df <= 0:
        return 1.0
    return betai(df / 2.0, 0.5, df / (df + t_stat * t_stat))


def p_value_chi2(chi2: float, dof: int) -> float:
    """P(Chi2 > chi2) à `dof` degrés de liberté."""
    if chi2 <= 0 or dof <= 0:
        return 1.0
    return gammq(dof / 2.0, chi2 / 2.0)


def t_critique_95(df: int) -> float:
    """Quantile t à 97,5 % (bilatéral 95 %), par recherche dichotomique."""
    if df < 1:
        return float("nan")
    bas, haut = 0.0, 100.0
    for _ in range(100):
        milieu = (bas + haut) / 2.0
        if p_value_t(milieu, df) > 0.05:
            bas = milieu
        else:
            haut = milieu
    return (bas + haut) / 2.0


# ---------------------------------------------------------------------------
# 3. Statistiques descriptives
# ---------------------------------------------------------------------------


def moyenne(xs: Sequence[float]) -> float:
    return sum(xs) / len(xs) if xs else float("nan")


def variance(xs: Sequence[float], ddof: int = 1) -> float:
    n = len(xs)
    if n - ddof <= 0:
        return float("nan")
    m = moyenne(xs)
    return sum((x - m) ** 2 for x in xs) / (n - ddof)


def ecart_type(xs: Sequence[float], ddof: int = 1) -> float:
    v = variance(xs, ddof)
    return math.sqrt(v) if v == v and v >= 0 else float("nan")


def mediane(xs: Sequence[float]) -> float:
    if not xs:
        return float("nan")
    s = sorted(xs)
    n = len(s)
    mid = n // 2
    return s[mid] if n % 2 else (s[mid - 1] + s[mid]) / 2.0


def quantile(xs: Sequence[float], q: float) -> float:
    """Quantile par interpolation linéaire (équivalent numpy 'linear')."""
    if not xs:
        return float("nan")
    s = sorted(xs)
    if len(s) == 1:
        return s[0]
    pos = q * (len(s) - 1)
    bas = int(math.floor(pos))
    haut = min(bas + 1, len(s) - 1)
    frac = pos - bas
    return s[bas] * (1 - frac) + s[haut] * frac


def rangs_percentiles(valeurs: Sequence[float]) -> list[float]:
    """Rang en percentile 0..100 (moyenne des rangs en cas d'ex aequo).

    Reproduit le comportement de pandas `rank(pct=True) * 100`.
    """
    n = len(valeurs)
    if n == 0:
        return []
    if n == 1:
        return [100.0]
    indices = sorted(range(n), key=lambda i: valeurs[i])
    rangs = [0.0] * n
    i = 0
    while i < n:
        j = i
        while j + 1 < n and valeurs[indices[j + 1]] == valeurs[indices[i]]:
            j += 1
        rang_moyen = (i + j) / 2.0 + 1.0  # rangs 1..n
        for k in range(i, j + 1):
            rangs[indices[k]] = rang_moyen / n * 100.0
        i = j + 1
    return rangs


def ic95(xs: Sequence[float]) -> tuple[float, float]:
    """Retourne (moyenne, demi-largeur de l'IC 95 %)."""
    n = len(xs)
    m = moyenne(xs)
    if n < 2:
        return m, float("nan")
    se = ecart_type(xs) / math.sqrt(n)
    return m, t_critique_95(n - 1) * se


def cohen_d(a: Sequence[float], b: Sequence[float]) -> float:
    """Cohen's d avec écart-type combiné."""
    na, nb = len(a), len(b)
    if na < 2 or nb < 2:
        return float("nan")
    va, vb = variance(a), variance(b)
    pooled = math.sqrt(((na - 1) * va + (nb - 1) * vb) / (na + nb - 2))
    if pooled == 0:
        return float("nan")
    return (moyenne(a) - moyenne(b)) / pooled


# ---------------------------------------------------------------------------
# 4. Tests d'hypothèses
# ---------------------------------------------------------------------------


def anova_un_facteur(groupes: Sequence[Sequence[float]]) -> dict:
    """ANOVA à un facteur. `groupes` : liste d'échantillons."""
    groupes = [g for g in groupes if len(g) >= 1]
    k = len(groupes)
    n_total = sum(len(g) for g in groupes)
    if k < 2 or n_total <= k:
        return {"applicable": False, "raison": "Groupes insuffisants"}

    toutes = [x for g in groupes for x in g]
    moy_gen = moyenne(toutes)

    ss_inter = sum(len(g) * (moyenne(g) - moy_gen) ** 2 for g in groupes)
    ss_intra = sum((x - moyenne(g)) ** 2 for g in groupes for x in g)

    df_inter, df_intra = k - 1, n_total - k
    if df_intra <= 0 or ss_intra <= 0:
        return {"applicable": False, "raison": "Variance intra nulle"}

    ms_inter, ms_intra = ss_inter / df_inter, ss_intra / df_intra
    f_stat = ms_inter / ms_intra
    p = p_value_f(f_stat, df_inter, df_intra)

    # Eta-carré : part de variance expliquée par le facteur.
    eta2 = ss_inter / (ss_inter + ss_intra)

    return {
        "applicable": True,
        "f_statistic": f_stat,
        "p_value": p,
        "significatif": p < ALPHA,
        "df_inter": df_inter,
        "df_intra": df_intra,
        "eta_carre": eta2,
        "n_groupes": k,
        "n_observations": n_total,
    }


def test_t_welch(a: Sequence[float], b: Sequence[float]) -> dict:
    """Test t de Welch (variances inégales, bilatéral)."""
    na, nb = len(a), len(b)
    if na < 2 or nb < 2:
        return {"applicable": False}
    va, vb = variance(a), variance(b)
    se2 = va / na + vb / nb
    if se2 <= 0:
        return {"applicable": False}
    t_stat = (moyenne(a) - moyenne(b)) / math.sqrt(se2)
    # Degrés de liberté de Welch-Satterthwaite.
    num = se2 * se2
    den = (va / na) ** 2 / (na - 1) + (vb / nb) ** 2 / (nb - 1)
    df = num / den if den > 0 else float(na + nb - 2)
    p = p_value_t(t_stat, df)
    return {
        "applicable": True,
        "t_statistic": t_stat,
        "p_value": p,
        "df": df,
        "significatif": p < ALPHA,
    }


def chi2_independance(table: list[list[int]]) -> dict:
    """Chi-carré d'indépendance sur une table de contingence + V de Cramér."""
    lignes = len(table)
    if lignes < 2:
        return {"applicable": False, "raison": "Moins de 2 lignes"}
    colonnes = len(table[0])
    if colonnes < 2:
        return {"applicable": False, "raison": "Moins de 2 colonnes"}

    total = sum(sum(l) for l in table)
    if total == 0:
        return {"applicable": False, "raison": "Table vide"}

    tot_lignes = [sum(l) for l in table]
    tot_col = [sum(table[i][j] for i in range(lignes)) for j in range(colonnes)]

    chi2 = 0.0
    cellules_faibles = 0
    for i in range(lignes):
        for j in range(colonnes):
            attendu = tot_lignes[i] * tot_col[j] / total
            if attendu <= 0:
                continue
            if attendu < 5:
                cellules_faibles += 1
            chi2 += (table[i][j] - attendu) ** 2 / attendu

    dof = (lignes - 1) * (colonnes - 1)
    p = p_value_chi2(chi2, dof)
    k = min(lignes, colonnes) - 1
    cramer = math.sqrt(chi2 / (total * k)) if k > 0 else float("nan")

    return {
        "applicable": True,
        "chi2": chi2,
        "p_value": p,
        "degres_liberte": dof,
        "significatif": p < ALPHA,
        "cramer_v": cramer,
        "n": total,
        "cellules_effectif_faible": cellules_faibles,
        "cellules_total": lignes * colonnes,
    }


def spearman(x: Sequence[float], y: Sequence[float]) -> dict:
    """Corrélation de rangs de Spearman + p-value (approximation en t)."""
    n = len(x)
    if n < 3 or n != len(y):
        return {"applicable": False}
    rx, ry = rangs_percentiles(x), rangs_percentiles(y)
    mx, my = moyenne(rx), moyenne(ry)
    num = sum((a - mx) * (b - my) for a, b in zip(rx, ry))
    den = math.sqrt(
        sum((a - mx) ** 2 for a in rx) * sum((b - my) ** 2 for b in ry)
    )
    if den == 0:
        return {"applicable": False, "raison": "Variance de rangs nulle"}
    rho = num / den
    if abs(rho) >= 1.0:
        return {"applicable": True, "rho": rho, "p_value": 0.0, "significatif": True}
    t_stat = rho * math.sqrt((n - 2) / (1 - rho * rho))
    p = p_value_t(t_stat, n - 2)
    return {
        "applicable": True,
        "rho": rho,
        "p_value": p,
        "significatif": p < ALPHA,
        "n": n,
    }


# ---------------------------------------------------------------------------
# 5. Shrinkage bayésien empirique
# ---------------------------------------------------------------------------


def shrinkage_empirique(groupes: dict[str, Sequence[float]]) -> dict:
    """Régularise les moyennes de groupe vers la moyenne générale.

    Indispensable ici : la plupart des universités ne comptent que 2-5 joueurs
    par poste. Une moyenne brute sur 2 joueurs n'est pas comparable à une
    moyenne sur 20 ; sans régularisation, le classement est dominé par le
    bruit d'échantillonnage.

    Estimateur de type James-Stein :

        score_regularise = (n * moyenne_groupe + k * moyenne_generale) / (n + k)

    où k = variance_intra / variance_inter est estimé sur les données. Plus un
    groupe est petit, plus son score est tiré vers la moyenne générale.

    Retourne les moyennes brutes, régularisées, et le poids k utilisé.
    """
    groupes = {g: list(v) for g, v in groupes.items() if len(v) >= 1}
    if len(groupes) < 2:
        return {"applicable": False}

    toutes = [x for v in groupes.values() for x in v]
    moy_generale = moyenne(toutes)

    # Variance intra (dans les groupes) : moyenne pondérée des variances.
    poids_total, somme_var = 0, 0.0
    for v in groupes.values():
        if len(v) >= 2:
            somme_var += (len(v) - 1) * variance(v)
            poids_total += len(v) - 1
    var_intra = somme_var / poids_total if poids_total > 0 else variance(toutes)

    # Variance inter : variance des moyennes de groupe, corrigée du bruit.
    # La variance observée entre moyennes de groupe contient déjà du bruit
    # d'échantillonnage (var_intra / n). On le retranche pour estimer la
    # variance « vraie » entre groupes.
    moyennes_groupes = [moyenne(v) for v in groupes.values()]
    var_observee = variance(moyennes_groupes)
    n_moyen = moyenne([len(v) for v in groupes.values()])
    var_inter_brute = var_observee - var_intra / n_moyen

    # Cas dégénéré : la dispersion observée entre groupes n'excède pas ce que
    # le simple hasard produirait. Il n'y a alors AUCUN signal inter-groupes
    # détectable, et le classement régularisé est plat par construction. On le
    # signale explicitement plutôt que de publier un classement vide de sens.
    signal_detectable = var_inter_brute > 0
    var_inter = max(var_inter_brute, 1e-9)

    k = var_intra / var_inter if var_inter > 0 else float("inf")
    k = min(k, 1e6)

    resultats = {}
    for nom, v in groupes.items():
        n = len(v)
        brute = moyenne(v)
        regularisee = (n * brute + k * moy_generale) / (n + k)
        resultats[nom] = {
            "n": n,
            "moyenne_brute": brute,
            "moyenne_regularisee": regularisee,
            "retrait": brute - regularisee,
        }

    return {
        "applicable": True,
        "k": k,
        "moyenne_generale": moy_generale,
        "variance_intra": var_intra,
        "variance_inter": var_inter,
        "variance_inter_brute": var_inter_brute,
        "signal_detectable": signal_detectable,
        "groupes": resultats,
    }


def validation_moities(
    groupes: dict[str, Sequence[float]], graine: int = 42, n_tirages: int = 200
) -> dict:
    """Teste si le classement des groupes est reproductible (split-half).

    C'est le test décisif, et il n'est pas circulaire : on coupe aléatoirement
    les membres de chaque groupe en deux moitiés, on classe les groupes sur la
    moitié A, puis on mesure la corrélation de ce classement avec celui obtenu
    sur la moitié B. Si l'effet de groupe était réel, les deux moitiés
    devraient concorder.

    Une corrélation moyenne proche de 0 signifie que le classement n'est pas
    reproductible : il reflète du bruit d'échantillonnage, pas un effet stable.
    """
    import random

    utilisables = {g: list(v) for g, v in groupes.items() if len(v) >= 4}
    if len(utilisables) < 3:
        return {"applicable": False, "raison": "Trop peu de groupes de taille >= 4"}

    rng = random.Random(graine)
    correlations = []
    for _ in range(n_tirages):
        moy_a, moy_b = {}, {}
        for nom, valeurs in utilisables.items():
            melange = valeurs[:]
            rng.shuffle(melange)
            milieu = len(melange) // 2
            a, b = melange[:milieu], melange[milieu:]
            if len(a) < 2 or len(b) < 2:
                continue
            moy_a[nom] = moyenne(a)
            moy_b[nom] = moyenne(b)
        communs = sorted(set(moy_a) & set(moy_b))
        if len(communs) < 3:
            continue
        res = spearman([moy_a[c] for c in communs], [moy_b[c] for c in communs])
        if res.get("applicable"):
            correlations.append(res["rho"])

    if not correlations:
        return {"applicable": False, "raison": "Aucun tirage exploitable"}

    moy_rho = moyenne(correlations)
    return {
        "applicable": True,
        "rho_moyen": moy_rho,
        "rho_median": mediane(correlations),
        "rho_min": min(correlations),
        "rho_max": max(correlations),
        "part_tirages_positifs": sum(1 for r in correlations if r > 0)
        / len(correlations),
        "n_tirages": len(correlations),
        "n_groupes": len(utilisables),
        "interpretation": interpreter_force(moy_rho, "rho"),
    }


# ---------------------------------------------------------------------------
# 6. Interprétation
# ---------------------------------------------------------------------------


def interpreter_force(valeur: float, type_: str = "r") -> str:
    """Traduit une taille d'effet en qualificatif."""
    if valeur != valeur:  # NaN
        return "indéterminée"
    v = abs(valeur)
    if type_ in ("r", "rho", "cramer"):
        seuils = [(0.1, "négligeable"), (0.3, "faible"), (0.5, "modérée")]
        defaut = "forte"
    elif type_ == "d":
        seuils = [(0.2, "négligeable"), (0.5, "petite"), (0.8, "moyenne")]
        defaut = "grande"
    elif type_ == "eta2":
        seuils = [(0.01, "négligeable"), (0.06, "petite"), (0.14, "moyenne")]
        defaut = "grande"
    else:
        return "indéterminée"
    for seuil, label in seuils:
        if v < seuil:
            return label
    return defaut
