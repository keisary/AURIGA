"""AURIGA - Conversion XGBPath → AST de conditions (adapté d'einherjar).

Einher est défini par une condition explicable. XGBoost produit des chemins
AND ; on les convertit en Condition (atome) ou ConditionNode (AND).

Simplification : enlève les bornes redondantes (RSI<70 AND RSI<50 → RSI<50).
"""
from __future__ import annotations

import logging

from auriga.research.path_extractor import XGBPath
from auriga.types import Condition, ConditionNode

logger = logging.getLogger(__name__)

OP_MAP = {"<": "<", "<=": "<=", ">": ">", ">=": ">=", "==": "==", "!=": "!="}


def path_to_ast(path: XGBPath) -> Condition | ConditionNode:
    """Convertit un chemin en AST de conditions (AND des atomes)."""
    if len(path.conditions) == 0:
        raise ValueError("Chemin vide : impossible de construire un AST")

    conditions = [
        Condition(feature_ref=feat, operator=OP_MAP.get(op, op), value=value)
        for feat, op, value in path.conditions
    ]

    if len(conditions) == 1:
        return conditions[0]

    result: Condition | ConditionNode = conditions[0]
    for c in conditions[1:]:
        result = ConditionNode(op="AND", left=result, right=c)
    return result


def simplify_ast(ast: Condition | ConditionNode) -> Condition | ConditionNode:
    """Simplifie un AST AND : fusionne les bornes redondantes sur une feature.

    Exemple : (RSI<70 AND RSI<50) → RSI<50
              (RSI>10 AND RSI>20) → RSI>20
    """
    if isinstance(ast, Condition):
        return ast

    # Collecter les atomes AND (récursif)
    atoms: list[Condition] = []

    def collect(node: Condition | ConditionNode) -> None:
        if isinstance(node, Condition):
            atoms.append(node)
            return
        if node.op == "AND":
            collect(node.left)
            collect(node.right)
        else:
            atoms.append(node)  # OR/NOT : on ne simplifie pas

    collect(ast)
    if len(atoms) == len(_flatten(ast)):
        pass  # pas de changement structurel

    # Fusionner par feature : pour une même feature, garder la borne la plus stricte
    by_feature: dict[str, Condition] = {}
    for a in atoms:
        feat = a.feature_ref
        if feat not in by_feature:
            by_feature[feat] = a
            continue
        existing = by_feature[feat]
        merged = _merge_same_feature(existing, a)
        if merged is not None:
            by_feature[feat] = merged
        else:
            # Impossible de fusionner en une seule borne → garder les deux
            by_feature[feat + "\x00" + str(len(by_feature))] = a

    merged_atoms = list(by_feature.values())
    if len(merged_atoms) == 1:
        return merged_atoms[0]
    result: Condition | ConditionNode = merged_atoms[0]
    for c in merged_atoms[1:]:
        result = ConditionNode(op="AND", left=result, right=c)
    return result


def _flatten(ast: Condition | ConditionNode) -> list[Condition | ConditionNode]:
    """Retourne tous les nœuds (pour le comptage)."""
    out: list[Condition | ConditionNode] = []

    def walk(n: Condition | ConditionNode) -> None:
        out.append(n)
        if isinstance(n, ConditionNode):
            walk(n.left)
            walk(n.right)

    walk(ast)
    return out


def _merge_same_feature(a: Condition, b: Condition) -> Condition | None:
    """Fusionne deux bornes sur la même feature si possible, sinon None."""
    lo = {"<", "<="}
    hi = {">", ">="}
    both_increasing = a.operator in hi and b.operator in hi
    both_decreasing = a.operator in lo and b.operator in lo
    equal = a.operator == "==" and b.operator == "==" and a.value == b.value

    if equal:
        return a
    if both_increasing:
        # Garder la borne la plus haute : max(a.value, b.value)
        return a if a.value >= b.value else b
    if both_decreasing:
        # Garder la borne la plus basse : min(a.value, b.value)
        return a if a.value <= b.value else b
    return None  # bornes de nature différente (inf + sup) : on garde les deux