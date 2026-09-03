"""AURIGA - Pricing Black-Scholes pour les options (évaluation en backtest).

Contexte : Alpaca ne fournit PAS de prix d'options historiques gratuits.
Pour backtester les spreads définis-risque, on estime les prix d'options à
partir du sous-jacent via Black-Scholes (avec une vol implicite estimée).

Formules standard :
- Call : C = S·N(d1) − K·e^(−rT)·N(d2)
- Put  : P = K·e^(−rT)·N(−d2) − S·N(−d1)
- d1 = [ln(S/K) + (r + σ²/2)·T] / (σ·√T)
- d2 = d1 − σ·√T
"""
from __future__ import annotations

import math
from dataclasses import dataclass


def norm_cdf(x: float) -> float:
    """Fonction de répartition de la loi normale standard."""
    return 0.5 * (1.0 + math.erf(x / math.sqrt(2.0)))


@dataclass
class OptionPrice:
    """Prix et grecques d'une option."""

    price: float
    delta: float
    gamma: float
    theta: float
    vega: float
    intrinsic: float
    extrinsic: float


def _d1_d2(S: float, K: float, T: float, r: float, sigma: float) -> tuple[float, float]:
    sigma_sqrt_t = sigma * math.sqrt(T)
    if sigma_sqrt_t <= 1e-12 or S <= 0 or K <= 0:
        return 0.0, 0.0
    d1 = (math.log(S / K) + (r + 0.5 * sigma * sigma) * T) / sigma_sqrt_t
    d2 = d1 - sigma_sqrt_t
    return d1, d2


def black_scholes(
    S: float,
    K: float,
    T: float,  # années jusqu'à expiration
    r: float = 0.04,
    sigma: float = 0.30,
    option_type: str = "call",
) -> OptionPrice:
    """Prix Black-Scholes + grecques principales.

    Args:
        S : prix du sous-jacent
        K : strike
        T : temps jusqu'à expiration en années
        r : taux sans risque (défaut 4%)
        sigma : volatilité annualisée (défaut 30%)
        option_type : 'call' | 'put'
    """
    is_call = option_type.lower() == "call"

    if T <= 0:
        # À expiration : valeur intrinsèque seulement
        intrinsic = max(S - K, 0.0) if is_call else max(K - S, 0.0)
        return OptionPrice(
            price=intrinsic, delta=1.0 if is_call and S > K else (0.0 if not is_call and S < K else 0.5),
            gamma=0.0, theta=0.0, vega=0.0,
            intrinsic=intrinsic, extrinsic=0.0,
        )

    d1, d2 = _d1_d2(S, K, T, r, sigma)
    if is_call:
        price = S * norm_cdf(d1) - K * math.exp(-r * T) * norm_cdf(d2)
        delta = norm_cdf(d1)
        intrinsic = max(S - K, 0.0)
    else:
        price = K * math.exp(-r * T) * norm_cdf(-d2) - S * norm_cdf(-d1)
        delta = -norm_cdf(-d1)
        intrinsic = max(K - S, 0.0)

    # Gamma (identique call/put), vega, theta (approximations usuelles)
    phi_d1 = math.exp(-0.5 * d1 * d1) / math.sqrt(2.0 * math.pi)
    gamma = phi_d1 / (S * sigma * math.sqrt(T)) if S > 0 and sigma > 0 else 0.0
    vega = S * phi_d1 * math.sqrt(T) / 100.0  # par point de vol (÷100)

    # Theta approximatif (par jour, ÷365)
    theta = -S * phi_d1 * sigma / (2.0 * math.sqrt(T)) / 365.0
    if not is_call:
        theta += r * K * math.exp(-r * T) * norm_cdf(-d2) / 365.0
    else:
        theta -= r * K * math.exp(-r * T) * norm_cdf(d2) / 365.0

    return OptionPrice(
        price=max(price, 0.01),  # plancher 1 centime
        delta=delta,
        gamma=gamma,
        theta=theta,
        vega=vega,
        intrinsic=intrinsic,
        extrinsic=max(price - intrinsic, 0.0),
    )


def implied_vol_guess(option_type: str, S: float, K: float, price: float, T: float) -> float:
    """Estime la vol implicite par bisection (fallback si IV non dispo)."""
    if T <= 0 or price <= 0:
        return 0.30
    lo, hi = 0.01, 3.0
    for _ in range(60):
        mid = (lo + hi) / 2
        p = black_scholes(S, K, T, sigma=mid, option_type=option_type).price
        if p < price:
            lo = mid
        else:
            hi = mid
    return (lo + hi) / 2
