from __future__ import annotations

import os
from unittest.mock import patch

import pytest


class TestLeagueConfigFiltering:
    """Test league allowlist/blocklist filtering from settings."""

    def test_no_filter_processes_all(self):
        """When neither allowlist nor blocklist is set, all leagues are processed."""
        env = {
            "DATABASE_URL": "postgresql://localhost/test",
            "DATABASE_URL_SYNC": "postgresql://localhost/test",
            "LEAGUE_ALLOWLIST": "",
            "LEAGUE_BLOCKLIST": "",
        }
        with patch.dict(os.environ, env, clear=True):
            from sports_common.config import Settings

            settings = Settings()

            assert settings.should_process_league("premier_league") is True
            assert settings.should_process_league("la_liga") is True

    def test_allowlist_only(self):
        """When allowlist is set, only those leagues are processed."""
        env = {
            "DATABASE_URL": "postgresql://localhost/test",
            "DATABASE_URL_SYNC": "postgresql://localhost/test",
            "LEAGUE_ALLOWLIST": "premier_league,la_liga",
            "LEAGUE_BLOCKLIST": "",
        }
        with patch.dict(os.environ, env, clear=True):
            from sports_common.config import Settings

            settings = Settings()

            assert settings.should_process_league("premier_league") is True
            assert settings.should_process_league("la_liga") is True
            assert settings.should_process_league("nfl") is False

    def test_blocklist_excludes(self):
        """When blocklist is set, those leagues are excluded."""
        env = {
            "DATABASE_URL": "postgresql://localhost/test",
            "DATABASE_URL_SYNC": "postgresql://localhost/test",
            "LEAGUE_ALLOWLIST": "",
            "LEAGUE_BLOCKLIST": "premier_league",
        }
        with patch.dict(os.environ, env, clear=True):
            from sports_common.config import Settings

            settings = Settings()

            assert settings.should_process_league("premier_league") is False
            assert settings.should_process_league("la_liga") is True

    def test_allowlist_then_blocklist(self):
        """Allowlist is applied first, then blocklist removes entries."""
        env = {
            "DATABASE_URL": "postgresql://localhost/test",
            "DATABASE_URL_SYNC": "postgresql://localhost/test",
            "LEAGUE_ALLOWLIST": "premier_league,la_liga,nfl",
            "LEAGUE_BLOCKLIST": "premier_league",
        }
        with patch.dict(os.environ, env, clear=True):
            from sports_common.config import Settings

            settings = Settings()

            assert settings.should_process_league("premier_league") is False
            assert settings.should_process_league("la_liga") is True
            assert settings.should_process_league("nfl") is True


class TestLeagueConfigProperties:
    """Test the league property accessors."""

    def test_league_allowlist_set(self):
        """Test parsing of comma-separated allowlist."""
        env = {
            "DATABASE_URL": "postgresql://localhost/test",
            "DATABASE_URL_SYNC": "postgresql://localhost/test",
            "LEAGUE_ALLOWLIST": "premier_league, la_liga , bundesliga",
            "LEAGUE_BLOCKLIST": "",
        }
        with patch.dict(os.environ, env, clear=True):
            from sports_common.config import Settings

            settings = Settings()

            assert settings.league_allowlist_set == {"premier_league", "la_liga", "bundesliga"}

    def test_league_blocklist_set(self):
        """Test parsing of comma-separated blocklist."""
        env = {
            "DATABASE_URL": "postgresql://localhost/test",
            "DATABASE_URL_SYNC": "postgresql://localhost/test",
            "LEAGUE_ALLOWLIST": "",
            "LEAGUE_BLOCKLIST": "premier_league, nfl",
        }
        with patch.dict(os.environ, env, clear=True):
            from sports_common.config import Settings

            settings = Settings()

            assert settings.league_blocklist_set == {"premier_league", "nfl"}

    def test_empty_strings(self):
        """Test that empty strings result in empty sets."""
        env = {
            "DATABASE_URL": "postgresql://localhost/test",
            "DATABASE_URL_SYNC": "postgresql://localhost/test",
            "LEAGUE_ALLOWLIST": "",
            "LEAGUE_BLOCKLIST": "",
        }
        with patch.dict(os.environ, env, clear=True):
            from sports_common.config import Settings

            settings = Settings()

            assert settings.league_allowlist_set == set()
            assert settings.league_blocklist_set == set()
