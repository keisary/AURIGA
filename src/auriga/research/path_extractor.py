"""AURIGA - Extraction des chemins d'arbres XGBoost (adapté d'einherjar).

Chaque arbre d'un GBDT est parcouru racine → feuille ; chaque feuille donne
un XGBPath : la liste des conditions (feature, op, seuil) menant à elle,
plus le score (valeur de la feuille).

Support xgboost (get_dump texte) et sklearn (Tree interne).
"""
from __future__ import annotations

import logging
import re
from dataclasses import dataclass
from typing import Any

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class XGBPath:
    """Un chemin racine→feuille dans un arbre GBDT."""

    conditions: tuple[tuple[str, str, float], ...]
    score: float
    tree_idx: int
    path_idx: int


# ---------------------------------------------------------------------------
# Parser xgboost (dump texte)
# ---------------------------------------------------------------------------

_NODE_RE = re.compile(
    r"^(\d+):\[(.+?)\s*([<>=!]+)\s*([\-\d\.eE+]+)\]\s*yes=(\d+),no=(\d+),missing=(\d+)"
)
_LEAF_RE = re.compile(r"^(\d+):leaf=([\-\d\.eE+]+)")


def parse_xgb_dump(dump_str: str, tree_idx: int = 0) -> list[XGBPath]:
    """Parse le dump texte d'un arbre XGBoost → liste de chemins."""
    nodes: dict[int, dict] = {}
    for line in dump_str.strip().split("\n"):
        line = line.strip()
        m = _NODE_RE.match(line)
        if m:
            nodes[int(m.group(1))] = {
                "type": "internal",
                "feature": m.group(2),
                "op": m.group(3),
                "threshold": float(m.group(4)),
                "yes": int(m.group(5)),
                "no": int(m.group(6)),
                "missing": int(m.group(7)),
            }
            continue
        m = _LEAF_RE.match(line)
        if m:
            nodes[int(m.group(1))] = {"type": "leaf", "value": float(m.group(2))}
    if not nodes:
        return []

    # Racine = nœud jamais référencé comme enfant
    target_ids = set()
    for nd in nodes.values():
        if nd["type"] == "internal":
            target_ids.add(nd["yes"])
            target_ids.add(nd["no"])
    roots = [nid for nid in nodes if nid not in target_ids]
    if not roots:
        return []

    paths: list[XGBPath] = []
    _walk(roots[0], [], nodes, paths, tree_idx)
    return paths


def _walk(
    node_id: int,
    conditions: list[tuple[str, str, float]],
    nodes: dict[int, dict],
    out: list[XGBPath],
    tree_idx: int,
) -> None:
    node = nodes.get(node_id)
    if node is None:
        return
    if node["type"] == "leaf":
        out.append(
            XGBPath(
                conditions=tuple(conditions),
                score=node["value"],
                tree_idx=tree_idx,
                path_idx=len(out),
            )
        )
        return

    feat = node["feature"]
    op = node["op"]
    thr = node["threshold"]

    if op == "<":
        yes_cond, no_cond = (feat, "<", thr), (feat, ">=", thr)
    elif op == "<=":
        yes_cond, no_cond = (feat, "<=", thr), (feat, ">", thr)
    elif op == ">":
        yes_cond, no_cond = (feat, ">", thr), (feat, "<=", thr)
    elif op == ">=":
        yes_cond, no_cond = (feat, ">=", thr), (feat, "<", thr)
    elif op == "==":
        yes_cond, no_cond = (feat, "==", thr), (feat, "!=", thr)
    elif op == "!=":
        yes_cond, no_cond = (feat, "!=", thr), (feat, "==", thr)
    else:
        return

    _walk(node["yes"], conditions + [yes_cond], nodes, out, tree_idx)
    _walk(node["no"], conditions + [no_cond], nodes, out, tree_idx)


# ---------------------------------------------------------------------------
# Parser sklearn
# ---------------------------------------------------------------------------

def parse_sklearn_tree(tree: Any, tree_idx: int) -> list[XGBPath]:
    """Parse un arbre sklearn (tree_) → liste de chemins."""
    children_left = tree.children_left
    children_right = tree.children_right
    feature = tree.feature
    threshold = tree.threshold
    value = tree.value  # shape (n_nodes, 1, 1)

    paths: list[XGBPath] = []
    _walk_sklearn(
        node_id=0,
        conditions=[],
        children_left=children_left,
        children_right=children_right,
        feature=feature,
        threshold=threshold,
        value=value,
        out=paths,
        tree_idx=tree_idx,
    )
    return paths


def _walk_sklearn(
    node_id: int,
    conditions: list[tuple[str, str, float]],
    children_left: Any,
    children_right: Any,
    feature: Any,
    threshold: Any,
    value: Any,
    out: list[XGBPath],
    tree_idx: int,
) -> None:
    if children_left[node_id] == -1:  # feuille
        score = float(value[node_id][0][0])
        out.append(
            XGBPath(
                conditions=tuple(conditions),
                score=score,
                tree_idx=tree_idx,
                path_idx=len(out),
            )
        )
        return

    f_idx = int(feature[node_id])
    thr = float(threshold[node_id])
    yes_cond = (f"f{f_idx}", "<", thr) if False else (f"f{f_idx}", "<=", thr)
    no_cond = (f"f{f_idx}", ">", thr)
    _walk_sklearn(
        children_left[node_id], conditions + [yes_cond],
        children_left, children_right, feature, threshold, value, out, tree_idx,
    )
    _walk_sklearn(
        children_right[node_id], conditions + [no_cond],
        children_left, children_right, feature, threshold, value, out, tree_idx,
    )


# ---------------------------------------------------------------------------
# API unifiée
# ---------------------------------------------------------------------------

def extract_paths(
    model: Any,
    backend: str,
    feature_names: list[str],
    max_paths: int = 200,
) -> list[XGBPath]:
    """Extrait les chemins de TOUS les arbres du modèle.

    Args:
        model : XGBRegressor ou GradientBoostingRegressor
        backend : 'xgboost' | 'sklearn'
        feature_names : noms des features (pour mapper fN → nom)
        max_paths : cap global sur le nombre de chemins retournés

    Returns:
        Liste de XGBPath (limité à max_paths, triés par |score| décroissant).
    """
    all_paths: list[XGBPath] = []

    if backend == "xgboost":
        booster = model.get_booster()
        dump = booster.get_dump(with_stats=False)
        for ti, tree_dump in enumerate(dump):
            paths = parse_xgb_dump(tree_dump, tree_idx=ti)
            all_paths.extend(paths)
    else:
        estimators = model.estimators_
        for ti, est in enumerate(estimators):
            tree = est[0].tree_ if hasattr(est, "__len__") else est.tree_
            paths = parse_sklearn_tree(tree, tree_idx=ti)
            all_paths.extend(paths)

    # Mapper fN → nom de feature
    mapped: list[XGBPath] = []
    for p in all_paths:
        conds = []
        for feat, op, thr in p.conditions:
            if feat.startswith("f") and feat[1:].isdigit():
                fidx = int(feat[1:])
                name = feature_names[fidx] if fidx < len(feature_names) else feat
            else:
                name = feat
            conds.append((name, op, thr))
        mapped.append(
            XGBPath(
                conditions=tuple(conds),
                score=p.score,
                tree_idx=p.tree_idx,
                path_idx=p.path_idx,
            )
        )

    # Tri par |score| décroissant (les feuilles les plus extrêmes d'abord)
    mapped.sort(key=lambda p: abs(p.score), reverse=True)
    return mapped[:max_paths]
