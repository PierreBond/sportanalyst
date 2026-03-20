from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from jinja2 import Environment, FileSystemLoader, select_autoescape


@dataclass
class MatchResearchSnapshot:
    """Assembled research snapshot for a single match (Section L.2).

    Aggregates tactical preview, market dynamics, probabilistic forecasts,
    SHAP explainability, and strategic recommendations.
    """

    match_id: str
    home_team: str
    away_team: str
    league: str = "Premier League"
    generated_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))

    home_win_prob: float = 0.0
    draw_prob: float = 0.0
    away_win_prob: float = 0.0
    predicted_home_score: float | None = None
    predicted_away_score: float | None = None

    shap_explanation: dict[str, Any] | None = None

    market_data: dict[str, Any] | None = None

    biometric_data: dict[str, Any] | None = None

    value_bets: list[dict[str, Any]] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        """Convert snapshot to dictionary for template rendering."""
        return {
            "match_id": self.match_id,
            "home_team": self.home_team,
            "away_team": self.away_team,
            "league": self.league,
            "generated_at": self.generated_at.strftime("%Y-%m-%d %H:%M UTC"),
            "home_win_prob": self.home_win_prob,
            "draw_prob": self.draw_prob,
            "away_win_prob": self.away_win_prob,
            "predicted_home_score": self.predicted_home_score,
            "predicted_away_score": self.predicted_away_score,
            "shap_explanation": self.shap_explanation or {},
            "market_data": self.market_data or {},
            "biometric_data": self.biometric_data or {},
            "value_bets": self.value_bets,
        }


TEMPLATE_DIR = Path(__file__).parent / "templates"

_env: Environment | None = None


def _get_env() -> Environment:
    """Get or create Jinja2 environment."""
    global _env
    if _env is None:
        _env = Environment(
            loader=FileSystemLoader(str(TEMPLATE_DIR)),
            autoescape=select_autoescape(["html", "xml"]),
            trim_blocks=True,
            lstrip_blocks=True,
        )
        _env.filters["default"] = lambda val, default: val if val is not None else default
    return _env


def build_html_report(snapshot: MatchResearchSnapshot) -> str:
    """Render a MatchResearchSnapshot as an HTML report.

    Args:
        snapshot: The assembled match research data.

    Returns:
        HTML string of the full match report.
    """
    env = _get_env()
    template = env.get_template("match_report.html")
    return template.render(**snapshot.to_dict())


def build_markdown_report(snapshot: MatchResearchSnapshot) -> str:
    """Render a MatchResearchSnapshot as a Markdown report.

    Args:
        snapshot: The assembled match research data.

    Returns:
        Markdown string of the full match report.
    """
    env = _get_env()
    template = env.get_template("match_report.md")
    return template.render(**snapshot.to_dict())


def build_report(snapshot: MatchResearchSnapshot, format: str = "html") -> str:
    """Build a report in the specified format.

    Args:
        snapshot: The assembled match research data.
        format: Output format - "html" or "markdown".

    Returns:
        Report string in the specified format.

    Raises:
        ValueError: If format is not supported.
    """
    if format == "html":
        return build_html_report(snapshot)
    elif format == "markdown":
        return build_markdown_report(snapshot)
    else:
        raise ValueError(f"Unsupported format: {format}. Use 'html' or 'markdown'.")
