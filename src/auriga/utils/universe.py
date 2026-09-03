"""AURIGA - Chargement de l'univers d'actifs depuis config/universe.yaml."""
from __future__ import annotations

from pathlib import Path

import yaml

# Univers par défaut (décision D7) - utilisé si le fichier est absent ou incomplet
DEFAULT_SYMBOLS = [
    "AAPL", "MSFT", "NVDA", "AMZN", "GOOGL", "META", "TSLA", "AMD", "AVGO",
    "JPM", "V", "MA",
    "XOM", "CVX", "CAT", "GE",
    "WMT", "COST", "KO", "PEP", "JNJ", "UNH",
    "SPY", "QQQ", "IWM",
]

DEFAULT_SECTORS = {
    "technology": ["AAPL", "MSFT", "NVDA", "AMZN", "GOOGL", "META", "TSLA", "AMD", "AVGO"],
    "financials": ["JPM", "V", "MA"],
    "energy": ["XOM", "CVX"],
    "industrials": ["CAT", "GE"],
    "consumer": ["WMT", "COST", "KO", "PEP"],
    "health": ["JNJ", "UNH"],
    "etf": ["SPY", "QQQ", "IWM"],
}


def load_universe(path: Path | str | None = None) -> dict:
    """Charge l'univers : {symbols: [...], sectors: {secteur: [symbols]}}.

    Fallback sur l'univers par défaut si le fichier est manquant/corrompu.
    """
    if path is None:
        path = Path(__file__).resolve().parents[3] / "config" / "universe.yaml"
    path = Path(path)

    if not path.exists():
        return {"symbols": list(DEFAULT_SYMBOLS), "sectors": dict(DEFAULT_SECTORS)}

    try:
        with open(path, encoding="utf-8") as f:
            raw = yaml.safe_load(f) or {}

        symbols = raw.get("symbols") or DEFAULT_SYMBOLS
        sectors = raw.get("sectors") or DEFAULT_SECTORS

        if not isinstance(symbols, list) or not symbols:
            symbols = DEFAULT_SYMBOLS
        if not isinstance(sectors, dict) or not sectors:
            sectors = DEFAULT_SECTORS

        return {"symbols": list(symbols), "sectors": dict(sectors)}
    except Exception:
        return {"symbols": list(DEFAULT_SYMBOLS), "sectors": dict(DEFAULT_SECTORS)}


def sector_of(symbol: str, universe: dict | None = None) -> str | None:
    """Retourne le secteur d'un symbole, ou None."""
    univ = universe or load_universe()
    for sector, symbols in univ.get("sectors", {}).items():
        if symbol in symbols:
            return sector
    return None
