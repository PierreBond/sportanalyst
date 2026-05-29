from __future__ import annotations

import os
from pathlib import Path
from typing import Any

import structlog
import yaml

logger = structlog.get_logger(__name__)


class LeagueConfig:
    """Dynamic league configuration loader.

    Loads league definitions from leagues.yaml and applies
    allowlist/blocklist filtering from environment or settings.
    """

    _instance: "LeagueConfig | None" = None
    _config: dict[str, Any] | None = None

    def __init__(self, config_path: Path | None = None) -> None:
        self._config_path = config_path or self._find_config_path()

    @classmethod
    def _find_config_path(cls) -> Path:
        """Find the leagues.yaml config file."""
        possible_paths = [
            Path("configs/leagues.yaml"),
            Path(__file__).parent.parent.parent / "configs" / "leagues.yaml",
            Path.cwd() / "configs" / "leagues.yaml",
        ]
        for path in possible_paths:
            if path.exists():
                return path
        logger.warning("leagues_config_not_found", paths=[str(p) for p in possible_paths])
        return possible_paths[0]

    @classmethod
    def get_instance(cls) -> "LeagueConfig":
        """Get singleton instance."""
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance

    @classmethod
    def reload(cls) -> "LeagueConfig":
        """Force reload of configuration."""
        cls._instance = cls()
        return cls._instance

    def _load_config(self) -> dict[str, Any]:
        """Load league configuration from YAML."""
        if self._config is not None:
            return self._config

        if not self._config_path.exists():
            logger.warning("leagues_config_missing", path=str(self._config_path))
            self._config = {"leagues": {}}
            return self._config

        try:
            with open(self._config_path) as f:
                self._config = yaml.safe_load(f) or {"leagues": {}}
            logger.info("leagues_config_loaded", path=str(self._config_path))
        except Exception as e:
            logger.error("leagues_config_load_failed", error=str(e))
            self._config = {"leagues": {}}

        return self._config

    def get_all_leagues(self) -> dict[str, dict[str, Any]]:
        """Get all configured leagues."""
        config = self._load_config()
        return config.get("leagues", {})

    def get_enabled_leagues(self) -> dict[str, dict[str, Any]]:
        """Get enabled leagues (respects default enabled flag)."""
        all_leagues = self.get_all_leagues()
        return {
            league_id: league_data
            for league_id, league_data in all_leagues.items()
            if league_data.get("enabled", True)
        }

    def get_league_info(self, league_id: str) -> dict[str, Any] | None:
        """Get info for a specific league."""
        return self.get_all_leagues().get(league_id)

    def get_display_name(self, league_id: str) -> str:
        """Get display name for a league."""
        info = self.get_league_info(league_id)
        if info:
            return info.get("display_name", league_id)
        return league_id.replace("_", " ").title()

    def get_sport(self, league_id: str) -> str:
        """Get sport type for a league."""
        info = self.get_league_info(league_id)
        return info.get("sport", "football") if info else "football"

    def get_provider_mapping(self, league_id: str) -> dict[str, str]:
        """Get provider to league ID mapping."""
        info = self.get_league_info(league_id)
        return info.get("provider_league_ids", {}) if info else {}

    def get_processing_order(self) -> list[str]:
        """Get ordered list of league IDs for processing priority."""
        config = self._load_config()
        return config.get("processing_order", [])

    def get_discovered_league_ids(self) -> list[str]:
        """Get list of all discovered league IDs."""
        return list(self.get_all_leagues().keys())


def get_league_config() -> LeagueConfig:
    """Get the league configuration singleton."""
    return LeagueConfig.get_instance()
