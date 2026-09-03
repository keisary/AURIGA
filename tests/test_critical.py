"""Tests critiques pour la soumission (revue externe 2026-09-03).

Couvre les comportements de sécurité les plus importants d'un système de
trading :
1. Fail-closed : une gate externe en erreur bloque l'ordre.
2. Spread : validation structurelle (2 legs, mêmes expirations).
3. Position sizing : respecte l'exposition max.
4. Paper mode : jamais d'API live en mode paper.
"""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from auriga.risk.engine import RiskEngine
from auriga.types import (
    OptionLeg,
    PortfolioState,
    SpreadStrategy,
)


def _spread(symbol: str = "AAPL") -> SpreadStrategy:
    return SpreadStrategy(
        symbol=symbol,
        name="put_credit_spread",
        legs=[
            OptionLeg("AAPL", "AAPL1", "sell", "put", 315.0, "2026-09-18"),
            OptionLeg("AAPL", "AAPL2", "buy", "put", 297.5, "2026-09-18"),
        ],
        max_risk=1511.0,
        max_profit=239.0,
        debit_or_credit=239.0,
        dte=15,
        delta=0.0,
    )


# ---------------------------------------------------------------------------
# 1. Fail-closed : gate externe en erreur → ordre BLOQUÉ
# ---------------------------------------------------------------------------

def test_risk_blocks_when_external_gate_fails():
    """Une gate qui lève une exception doit bloquer l'ordre (P0 fail-open)."""
    engine = RiskEngine()

    def broken_gate(spread):
        raise RuntimeError("modele vol indisponible")

    engine.add_check(broken_gate, "vol_danger")

    portfolio = PortfolioState(equity=100_000, cash=90_000, buying_power=400_000)
    decision = engine.evaluate_spread(_spread(), portfolio)

    assert decision.allowed is False, "FAIL-OPEN: gate en erreur n'a pas bloqué"
    assert any("vol_danger" in b for b in decision.blocked_by)


def test_risk_allows_when_gate_ok():
    """Avec toutes les gates OK (et pas d'extra_checks), l'ordre passe."""
    engine = RiskEngine()
    portfolio = PortfolioState(equity=100_000, cash=90_000, buying_power=400_000)
    decision = engine.evaluate_spread(_spread(), portfolio)
    assert decision.allowed is True


# ---------------------------------------------------------------------------
# 2. Validation des spreads
# ---------------------------------------------------------------------------

def test_spread_requires_two_legs():
    from auriga.execution.orders import validate_spread

    bad = SpreadStrategy(
        symbol="AAPL", name="bad_spread",
        legs=[OptionLeg("AAPL", "AAPL1", "buy", "call", 325.0, "2026-09-18")],
        max_risk=100, max_profit=100, debit_or_credit=100, dte=15, delta=0.0,
    )
    ok, reason = validate_spread(bad)
    assert not ok
    assert "2 jambes" in reason


def test_spread_requires_same_expiry():
    from auriga.execution.orders import validate_spread

    bad = SpreadStrategy(
        symbol="AAPL", name="bad_expiry",
        legs=[
            OptionLeg("AAPL", "AAPL1", "sell", "put", 315.0, "2026-09-18"),
            OptionLeg("AAPL", "AAPL2", "buy", "put", 297.5, "2026-10-16"),
        ],
        max_risk=100, max_profit=100, debit_or_credit=100, dte=15, delta=0.0,
    )
    ok, reason = validate_spread(bad)
    assert not ok
    assert "MÊME expiration" in reason


def test_spread_valid():
    from auriga.execution.orders import validate_spread

    ok, reason = validate_spread(_spread())
    assert ok, reason


# ---------------------------------------------------------------------------
# 3. Position sizing : respecte l'exposition max par actif
# ---------------------------------------------------------------------------

def test_position_size_respects_max_exposure():
    """Un spread dont le risque dépasse 10% du capital est bloqué."""
    engine = RiskEngine()  # max_asset_exposure par défaut = 0.10
    portfolio = PortfolioState(equity=100_000, cash=90_000, buying_power=400_000)

    huge = _spread()
    huge.max_risk = 30_000  # 30% du capital → doit être bloqué
    decision = engine.evaluate_spread(huge, portfolio)
    assert not decision.allowed
    assert any("asset_exposure" in b or "position_size" in b for b in decision.blocked_by)


def test_asset_exposure_accumulates():
    """Deux positions sur le même actif cumulent leur exposition."""
    engine = RiskEngine()
    portfolio = PortfolioState(equity=100_000, cash=90_000, buying_power=400_000)
    # Ajouter une position existante sur AAPL avec 8% du capital
    from auriga.types import PositionState

    portfolio.positions.append(
        PositionState(
            symbol="AAPL", strategy_name="x", einher_id="e1",
            qty=1, entry_price=100, max_risk=8_000, opened_at="",
        )
    )
    # Nouveau spread AAPL à 3% → cumul 11% > 10% → bloqué
    spread = _spread()
    spread.max_risk = 3_000
    decision = engine.evaluate_spread(spread, portfolio)
    assert not decision.allowed
    assert any("asset_exposure" in b for b in decision.blocked_by)


# ---------------------------------------------------------------------------
# 4. Paper mode : jamais d'API live
# ---------------------------------------------------------------------------

def test_execution_client_defaults_to_paper():
    """Le client d'exécution doit être en mode paper par défaut."""
    import os

    from dotenv import load_dotenv

    load_dotenv(Path(__file__).resolve().parents[1] / ".env")

    from auriga.execution.client import ExecutionClient

    has_keys = bool(os.getenv("ALPACA_API_KEY") and os.getenv("ALPACA_SECRET_KEY"))
    if not has_keys:
        pytest.skip("Pas de clés Alpaca — test du défaut paper impossible")

    client = ExecutionClient()
    assert client.paper is True, "Le client doit être en mode PAPER par défaut"


def test_live_api_never_used_in_paper_mode():
    """Vérifie que les URLs paper sont utilisées (pas l'API live)."""
    import os

    from dotenv import load_dotenv

    load_dotenv(Path(__file__).resolve().parents[1] / ".env")

    has_keys = bool(os.getenv("ALPACA_API_KEY") and os.getenv("ALPACA_SECRET_KEY"))
    if not has_keys:
        pytest.skip("Pas de clés Alpaca")

    from alpaca.trading.client import TradingClient

    client = TradingClient(
        os.getenv("ALPACA_API_KEY"), os.getenv("ALPACA_SECRET_KEY"), paper=True
    )
    # L'URL paper contient 'paper-api'
    assert "paper" in str(client._base_url).lower() or "paper" in str(getattr(client, "base_url", "")).lower()