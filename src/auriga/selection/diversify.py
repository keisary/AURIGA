"""AURIGA - Diversification : sélection d'Einhers NON redondants.

Problème : la recherche produit des Einhers quasi-jumeaux (mêmes features,
conditions proches) qui tradent pareil → capital dilué, risque concentré.

Méthode (adaptée du twin_clustering einherjar) :
1. Pour chaque Einher, extraire l'ensemble des features utilisées.
2. Similarité de Jaccard entre deux Einhers : |A ∩ B| / |A ∪ B|.
3. Si Jaccard >= seuil (0.7) → considérés redondants : on garde le mieux
   scoré, on écarte l'autre (greedy par score décroissant).

Sortie : sous-ensemble d'Einhers diversifiés.
"""
from __future__ import annotations

import logging

from auriga.selection.scoring import score_einher
from auriga.types import Condition, ConditionNode, Einher

logger = logging.getLogger(__name__)

JACCARD_THRESHOLD = 0.70


def features_of(einher: Einher) -> set[str]:
    """Extrait les features utilisées par la condition d'un Einher."""
    feats: set[str] = set()

    def walk(node) -> None:
        if isinstance(node, Condition):
            feats.add(node.feature_ref)
        elif isinstance(node, ConditionNode):
            walk(node.left)
            walk(node.right)

    walk(einher.condition)
    return feats


def jaccard(a: set[str], b: set[str]) -> float:
    """Similarité de Jaccard entre deux ensembles de features."""
    union = a | b
    if not union:
        return 0.0
    return len(a & b) / len(union)


def diversify(
    einhers: list[Einher],
    threshold: float = JACCARD_THRESHOLD,
    same_symbol_only: bool = True,
) -> list[Einher]:
    """Élimine les Einhers redondants (greedy par score décroissant).

    Args:
        einhers : candidats admis
        threshold : Jaccard au-delà duquel 2 Einhers sont redondants
        same_symbol_only : ne comparer que les Einhers du MÊME actif
            (deux règles sur AAPL et MSFT ne sont pas redondantes même
            avec les mêmes features)

    Returns:
        liste diversifiée, triée par score décroissant.
    """
    if len(einhers) <= 1:
        return einhers

    # Trier par score décroissant
    ranked = sorted(einhers, key=score_einher, reverse=True)

    selected: list[Einher] = []
    features_selected: list[tuple[str, set[str]]] = []  # (symbol, features)

    for ein in ranked:
        feats = features_of(einher=ein)
        redundant = False

        for sel_sym, sel_feats in features_selected:
            if same_symbol_only and sel_sym != ein.symbol:
                continue
            if jaccard(feats, sel_feats) >= threshold:
                redundant = True
                break

        if not redundant:
            selected.append(ein)
            features_selected.append((ein.symbol, feats))

    logger.info(
        "Diversification : %d → %d Einhers (seuil Jaccard %.2f)",
        len(einhers), len(selected), threshold,
    )
    return selected