"""AURIGA - Narratif quotidien généré par LLM (module NAR).

Le LLM écrit un rapport CLAIR des décisions du jour, ancré sur des FAITS
structurés fournis par le pipeline (P&L, positions, stratégies découvertes,
risk gates). Il ne DÉCIDE rien — les décisions viennent du moteur
déterministe (REQ-AI-001, D2 du cahier des charges).

Provider : API compatible OpenAI (OpenRouter par défaut). Configurable via
settings.yaml (narrative.provider / narrative.model) et .env
(OPENROUTER_API_KEY).
"""
from __future__ import annotations

import json
import logging
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import requests

from auriga.utils.config import get_config

logger = logging.getLogger(__name__)

SYSTEM_PROMPT = """Tu es le narrateur du système AURIGA, un agent autonome de recherche
quantitative qui trade des options définis-risque en paper trading.

Règles strictes :
1. Écris en FRANÇAIS, de façon claire et accessible (le lecteur peut être non-quant).
2. ANCRE-TOI UNIQUEMENT sur les faits fournis ci-dessous. N'invente RIEN.
   Les chiffres (P&L, positions, métriques) viennent du moteur, pas de toi.
3. Ne donne AUCUN conseil financier, aucune recommandation d'investissement.
4. Structure : (a) résumé du jour, (b) stratégies actives, (c) découvertes de la
   recherche, (d) gestion du risque, (e) perspective. Max 400 mots.
5. Ton : factuel, sobre, professionnel. Pas de jargon inutile."""


@dataclass
class NarrativeFacts:
    """Faits structurés du pipeline transmis au LLM."""

    date: str = ""
    portfolio: dict[str, Any] = field(default_factory=dict)
    positions: list[dict[str, Any]] = field(default_factory=list)
    new_strategies: list[dict[str, Any]] = field(default_factory=list)
    trades_today: list[dict[str, Any]] = field(default_factory=list)
    risk_events: list[dict[str, Any]] = field(default_factory=list)
    research_summary: dict[str, Any] = field(default_factory=dict)

    def to_prompt_block(self) -> str:
        """Sérialise les faits pour le prompt LLM."""
        return json.dumps(
            {
                "date": self.date,
                "portefeuille": self.portfolio,
                "positions": self.positions[:15],
                "nouvelles_strategies": self.new_strategies[:10],
                "trades_du_jour": self.trades_today[:20],
                "evenements_risque": self.risk_events[:10],
                "resume_recherche": self.research_summary,
            },
            ensure_ascii=False,
            indent=1,
            default=str,
        )


class NarrativeGenerator:
    """Génère le rapport quotidien via une API compatible OpenAI."""

    def __init__(self, api_key: str | None = None, model: str | None = None, base_url: str | None = None):
        cfg = get_config()
        nar = cfg.narrative
        self.api_key = api_key or cfg.openrouter_api_key
        self.model = model or cfg.llm_model  # AURIGA_LLM_MODEL prioritaire
        self.base_url = base_url or nar.get("base_url", "https://openrouter.ai/api/v1")
        self.max_tokens = int(nar.get("max_tokens", 1500))
        self.temperature = float(nar.get("temperature", 0.4))
        self._available = bool(self.api_key)

    @property
    def available(self) -> bool:
        return self._available

    def generate(self, facts: NarrativeFacts) -> tuple[str, bool]:
        """Génère le rapport. Retourne (texte, ok).

        Si pas de clé API → template factuel (mode dégradé, jamais d'hallucination).
        """
        if not self._available:
            return self._fallback_template(facts), False

        prompt = facts.to_prompt_block()
        try:
            resp = requests.post(
                f"{self.base_url}/chat/completions",
                headers={
                    "Authorization": f"Bearer {self.api_key}",
                    "Content-Type": "application/json",
                },
                json={
                    "model": self.model,
                    "messages": [
                        {"role": "system", "content": SYSTEM_PROMPT},
                        {"role": "user", "content": f"Faits du jour :\n{prompt}"},
                    ],
                    "max_tokens": self.max_tokens,
                    "temperature": self.temperature,
                },
                timeout=60,
            )
            resp.raise_for_status()
            data = resp.json()
            text = data["choices"][0]["message"]["content"].strip()
            return text, True
        except Exception as e:
            logger.error("Narratif LLM échoué (%s) → fallback template", e)
            return self._fallback_template(facts), False

    def _fallback_template(self, facts: NarrativeFacts) -> str:
        """Template factuel (sans LLM) — utilisé si API indisponible."""
        pf = facts.portfolio
        lines = [
            f"# Rapport AURIGA — {facts.date or datetime.now(timezone.utc).strftime('%Y-%m-%d')}",
            "",
            "## Résumé du jour (mode dégradé : narratif LLM indisponible)",
            f"- Capital : {pf.get('equity', 0):,.0f} $ | Cash : {pf.get('cash', 0):,.0f} $",
            f"- P&L du jour : {pf.get('day_pnl', 0):+,.0f} $ | P&L total : {pf.get('total_pnl', 0):+,.0f} $",
            f"- Positions ouvertes : {len(facts.positions)}",
            "",
        ]
        if facts.positions:
            lines.append("## Positions actives")
            for p in facts.positions[:10]:
                lines.append(
                    f"- {p.get('symbol', '?')} ({p.get('direction', '?')}) : "
                    f"risque {p.get('max_risk', 0):,.0f} $ — {p.get('rationale', '')}"
                )
        if facts.new_strategies:
            lines.append(f"\n## Nouvelles stratégies découvertes : {len(facts.new_strategies)}")
        if facts.risk_events:
            lines.append("\n## Événements de risque")
            for r in facts.risk_events[:5]:
                lines.append(f"- {r.get('detail', r)}")
        lines.append("\n*Rapport généré automatiquement par AURIGA. Pas un conseil financier.*")
        return "\n".join(lines)

    def save(self, text: str, output_dir: Path | str | None = None) -> Path:
        """Sauvegarde le rapport en Markdown horodaté."""
        cfg = get_config()
        if output_dir is None:
            output_dir = Path(cfg.storage.get("narratives", "outputs/narratives"))
        output_dir = Path(output_dir)
        output_dir.mkdir(parents=True, exist_ok=True)
        date = datetime.now(timezone.utc).strftime("%Y%m%d")
        path = output_dir / f"report_{date}.md"
        path.write_text(text, encoding="utf-8")
        logger.info("Narratif sauvegardé: %s", path)
        return path