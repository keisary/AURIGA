"""AURIGA - Interface CLI (module ORC).

Commandes :
  auriga research [--symbols AAPL,MSFT] [--horizons 6,24,48]   → mode recherche
  auriga run      [--dry-run] [--symbols ...]                  → recherche + trading
  auriga status                                                → état portefeuille
  auriga dashboard                                             → lancer Streamlit
  auriga collect                                                 → collecte données univers
"""
from __future__ import annotations

import argparse
import logging
import sys

logger = logging.getLogger("auriga.cli")


def _setup_logging(verbose: bool = False) -> None:
    level = logging.DEBUG if verbose else logging.INFO
    logging.basicConfig(
        level=level,
        format="%(asctime)s | %(name)s | %(levelname)s | %(message)s",
        stream=sys.stdout,
    )


def cmd_research(args) -> int:
    from auriga.orchestration.pipeline import run_research_mode

    symbols = args.symbols.split(",") if args.symbols else None
    horizons = [int(h) for h in args.horizons.split(",")] if args.horizons else None

    summary = run_research_mode(symbols=symbols, horizons_bars=horizons)
    import json

    print("\n=== RÉSUMÉ RECHERCHE ===")
    print(json.dumps(summary, indent=2, ensure_ascii=False))
    return 0


def cmd_run(args) -> int:
    from auriga.orchestration.pipeline import run_full

    symbols = args.symbols.split(",") if args.symbols else None
    horizons = [int(h) for h in args.horizons.split(",")] if args.horizons else None

    summary = run_full(
        symbols=symbols,
        horizons_bars=horizons,
        dry_run=args.dry_run,
    )
    import json

    print("\n=== RÉSUMÉ RUN COMPLET ===")
    print(json.dumps(summary, indent=2, ensure_ascii=False, default=str))
    return 0


def cmd_status(args) -> int:
    from auriga.orchestration.state import StateStore

    state = StateStore()
    positions = state.read_positions()
    cycles = state.read_cycles(limit=5)

    print(f"=== AURIGA STATUS ===")
    print(f"Positions suivies : {len(positions)}")
    for p in positions:
        print(f"  - {p.symbol} {p.direction} ({p.strategy_name}) "
              f"risque ${p.max_risk:,.0f} qty={p.qty} ouverte {p.opened_at[:10]}")
    print(f"\nDerniers cycles :")
    for c in reversed(cycles):
        mode = c.get("mode", "?")
        cand = c.get("candidats_total", c.get("signaux_declenches", "?"))
        print(f"  - {c.get('timestamp', '?')[:19]} [{mode}] {c}")
    return 0


def cmd_dashboard(args) -> int:
    import subprocess

    subprocess.run([sys.executable, "-m", "streamlit", "run",
                    "src/auriga/dashboard/app.py"])
    return 0


def cmd_collect(args) -> int:
    from dotenv import load_dotenv

    load_dotenv()
    from auriga.data.market_data import download_option_chains, download_universe
    from auriga.utils.universe import load_universe

    universe = load_universe()
    symbols = universe["symbols"]
    print(f"Collecte des données pour {len(symbols)} actifs...")
    download_universe(symbols, "1H")
    download_universe(symbols, "1D")
    download_option_chains(symbols)
    print("Collecte terminée.")
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="auriga", description="AURIGA - Autonomous Quant Research Agent")
    parser.add_argument("-v", "--verbose", action="store_true", help="logs DEBUG")
    sub = parser.add_subparsers(dest="command")

    # research
    p_res = sub.add_parser("research", help="mode recherche (aucun ordre)")
    p_res.add_argument("--symbols", help="actifs séparés par virgules")
    p_res.add_argument("--horizons", help="horizons en heures (6,24,48)")
    p_res.set_defaults(func=cmd_research)

    # run
    p_run = sub.add_parser("run", help="recherche + trading (dry-run par défaut)")
    p_run.add_argument("--dry-run", action="store_true", default=True, help="ne soumet pas d'ordres")
    p_run.add_argument("--no-dry-run", dest="dry_run", action="store_false", help="soumet les ordres paper")
    p_run.add_argument("--symbols", help="actifs séparés par virgules")
    p_run.add_argument("--horizons", help="horizons en heures")
    p_run.set_defaults(func=cmd_run)

    # status
    p_status = sub.add_parser("status", help="état du portefeuille")
    p_status.set_defaults(func=cmd_status)

    # dashboard
    p_dash = sub.add_parser("dashboard", help="lancer le dashboard Streamlit")
    p_dash.set_defaults(func=cmd_dashboard)

    # collect
    p_collect = sub.add_parser("collect", help="collecte des données univers")
    p_collect.set_defaults(func=cmd_collect)

    args = parser.parse_args(argv)
    _setup_logging(args.verbose)
    if not hasattr(args, "func"):
        parser.print_help()
        return 1
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())