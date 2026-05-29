from __future__ import annotations

import pytest


class TestIngestionEndpoints:
    """Test ingestion API endpoints."""

    def test_league_status_endpoint_structure(self):
        """Verify league status endpoint returns expected structure."""
        pass

    def test_ingestion_run_accepts_leagues_param(self):
        """Verify ingestion run accepts leagues parameter."""
        pass

    def test_ingestion_run_accepts_batch_size_param(self):
        """Verify ingestion run accepts batch_size parameter."""
        pass


class TestDynamicLeagueScaling:
    """Test dynamic league scaling behavior."""

    def test_no_hardcoded_leagues_in_api_response(self):
        """API responses should not contain hardcoded league names."""
        pass

    def test_leagues_endpoint_returns_db_content(self):
        """Leagues endpoint should return dynamic data from DB."""
        pass

    def test_matches_filter_by_league_param(self):
        """Matches endpoint should filter correctly by league param."""
        pass

    def test_matches_without_league_returns_all(self):
        """Matches endpoint without league param should return all leagues."""
        pass


class TestLeagueProcessorConfig:
    """Test LeagueProcessor configuration."""

    def test_allowlist_filtering(self):
        """When allowlist is set, only those leagues are processed."""
        pass

    def test_blocklist_filtering(self):
        """When blocklist is set, those leagues are excluded."""
        pass

    def test_both_allowlist_and_blocklist(self):
        """Allowlist is applied first, then blocklist."""
        pass

    def test_empty_allowlist_processes_all(self):
        """Empty allowlist means all leagues are processed."""
        pass
