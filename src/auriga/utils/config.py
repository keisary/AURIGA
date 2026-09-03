"""AURIGA - Configuration centrale.

Charge la configuration depuis config/settings.yaml + variables d'environnement
(.env). Fournit un objet Config unique accessible partout.
"""
from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import yaml

try:
    from dotenv import load_dotenv
except ImportError:  # pragma: no cover
    def load_dotenv(*_args, **_kwargs):  # type: ignore
        return False

ROOT_DIR = Path(__file__).resolve().parents[3]  # D:/midas_v2/AURIGA
CONFIG_DIR = ROOT_DIR / "config"


@dataclass
class Config:
    """Configuration AURIGA, chargée une seule fois."""

    raw: dict[str, Any] = field(default_factory=dict)

    @classmethod
    def load(cls, settings_path: Path | str | None = None) -> Config:
        load_dotenv(ROOT_DIR / ".env")
        path = Path(settings_path) if settings_path else CONFIG_DIR / "settings.yaml"
        with open(path, encoding="utf-8") as f:
            raw = yaml.safe_load(f) or {}
        return cls(raw=raw)

    def __getitem__(self, key: str) -> Any:
        return self.raw[key]

    def get(self, key: str, default: Any = None) -> Any:
        return self.raw.get(key, default)

    # --- Accès pratiques aux sous-sections ---
    @property
    def research(self) -> dict[str, Any]:
        return self.raw.get("research", {})

    @property
    def admission(self) -> dict[str, Any]:
        return self.raw.get("admission", {})

    @property
    def discovery(self) -> dict[str, Any]:
        return self.raw.get("discovery", {})

    @property
    def selection(self) -> dict[str, Any]:
        return self.raw.get("selection", {})

    @property
    def options(self) -> dict[str, Any]:
        return self.raw.get("options", {})

    @property
    def risk(self) -> dict[str, Any]:
        return self.raw.get("risk", {})

    @property
    def narrative(self) -> dict[str, Any]:
        return self.raw.get("narrative", {})

    @property
    def orchestration(self) -> dict[str, Any]:
        return self.raw.get("orchestration", {})

    @property
    def storage(self) -> dict[str, Any]:
        return self.raw.get("storage", {})

    # --- Environnement ---
    @property
    def alpaca_api_key(self) -> str | None:
        return os.getenv("ALPACA_API_KEY")

    @property
    def alpaca_secret_key(self) -> str | None:
        return os.getenv("ALPACA_SECRET_KEY")

    @property
    def alpaca_paper(self) -> bool:
        return os.getenv("ALPACA_PAPER", "true").lower() == "true"

    @property
    def openrouter_api_key(self) -> str | None:
        return os.getenv("OPENROUTER_API_KEY")

    @property
    def llm_model(self) -> str:
        """Modèle LLM : AURIGA_LLM_MODEL (env) sinon narrative.model (yaml)."""
        return os.getenv("AURIGA_LLM_MODEL") or self.raw.get("narrative", {}).get(
            "model", "deepseek/deepseek-chat"
        )

    @property
    def has_alpaca_credentials(self) -> bool:
        return bool(self.alpaca_api_key and self.alpaca_secret_key)


# Singleton global
_config: Config | None = None


def get_config() -> Config:
    """Retourne la configuration (chargée une seule fois)."""
    global _config
    if _config is None:
        _config = Config.load()
    return _config
