"""AURIGA - Helpers pour les symboles d'options OCC.

Format OCC : [SYMBOLE][YYMMDD][C/P][STRIKE x 1000 sur 8 chiffres]
Exemple : AAPL260916C00275000
  - symbole : AAPL
  - date    : 260916 → 2026-09-16 (expiration)
  - type    : C (call) ou P (put)
  - strike  : 00275000 → 275.00

Ces helpers servent à la fois au module options (lecture des chaînes) et au
module execution (construction des symboles pour les ordres multi-leg).
"""
from __future__ import annotations

import re
from datetime import datetime

# Symbole OCC complet : 1-6 lettres racine + 6 chiffres date + C/P + 8 chiffres strike
_OCC_RE = re.compile(r"^([A-Z]{1,6})(\d{6})([CP])(\d{8})$")


def parse_occ(option_symbol: str) -> dict | None:
    """Parse un symbole OCC → {root, expiry_yyyymmdd, type, strike}.

    Returns:
        dict avec 'root', 'expiry' (YYYY-MM-DD), 'type' ('call'|'put'),
        'strike' (float), ou None si le format est invalide.
    """
    m = _OCC_RE.match(option_symbol.strip().upper())
    if not m:
        return None
    root, yymmdd, cp, strike8 = m.groups()
    try:
        exp = datetime.strptime(yymmdd, "%y%m%d")
    except ValueError:
        return None
    strike = int(strike8) / 1000.0
    return {
        "root": root,
        "expiry": exp.strftime("%Y-%m-%d"),
        "type": "call" if cp == "C" else "put",
        "strike": strike,
    }


def build_occ(root: str, expiry: str, option_type: str, strike: float) -> str:
    """Construit un symbole OCC.

    Args:
        root : symbole du sous-jacent (ex: AAPL)
        expiry : 'YYYY-MM-DD'
        option_type : 'call' | 'put'
        strike : prix d'exercice (ex: 275.0)

    Returns:
        symbole OCC complet (ex: AAPL260916C00275000).
    """
    dt = datetime.strptime(expiry, "%Y-%m-%d")
    yymmdd = dt.strftime("%y%m%d")
    cp = "C" if option_type.lower() == "call" else "P"
    strike8 = f"{int(round(strike * 1000)):08d}"
    return f"{root.upper()}{yymmdd}{cp}{strike8}"


def days_to_expiry(expiry: str, ref: datetime | None = None) -> int:
    """Jours jusqu'à l'expiration (DTE)."""

    if ref is None:
        ref = datetime.now()
    exp = datetime.strptime(expiry, "%Y-%m-%d")
    return (exp.date() - ref.date()).days
