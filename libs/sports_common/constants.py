from __future__ import annotations

from enum import Enum


class Sport(str, Enum):
    FOOTBALL = "football"
    BASKETBALL = "basketball"
    BASEBALL = "baseball"
    HOCKEY = "hockey"
    SOCCER = "soccer"
    CRICKET = "cricket"
    NFL = "nfl"
    NBA = "nba"
    MLB = "mlb"
    NHL = "nhl"


class League(str, Enum):
    PREMIER_LEAGUE = "premier_league"
    LA_LIGA = "la_liga"
    SERIE_A = "serie_a"
    BUNDESLIGA = "bundensliga"
    LIGUE_1 = "ligue_1"
    MLS = "mls"
    NFL = "nfl"
    NBA = "nba"
    MLB = "mlb"
    NHL = "nhl"


class MatchStatus(str, Enum):
    SCHEDULED = "scheduled"
    LIVE = "live"
    FINISHED = "finished"
    POSTPONED = "postponed"
    CANCELLED = "cancelled"


class MarketType(str, Enum):
    MONEYLINE = "moneyline"
    SPREAD = "spread"
    TOTAL = "total"
    PROP = "prop"


class EventType(str, Enum):
    GOAL = "goal"
    SHOT = "shot"
    SHOT_ON_TARGET = "shot_on_target"
    FOUL = "foul"
    CARD = "card"
    SUBSTITUTION = "substitution"
    PENALTY = "penalty"
    OWN_GOAL = "own_goal"
    VAR = "var"
    KICKOFF = "kickoff"
    HALFTIME = "halftime"
    FULLTIME = "fulltime"


class BiometricMetricType(str, Enum):
    HRV = "hrv"
    RESTING_HR = "resting_hr"
    PLAYER_LOAD = "player_load"
    SPRINT_DIST = "sprint_dist"
    ACCELERATION = "acceleration"
    SLEEP_DURATION = "sleep_duration"
    SLEEP_QUALITY = "sleep_quality"
    RECOVERY_SCORE = "recovery_score"


class SentimentSource(str, Enum):
    TWITTER = "twitter"
    REDDIT = "reddit"
    NEWS = "news"


class ModelStage(str, Enum):
    NONE = "none"
    STAGING = "staging"
    PRODUCTION = "production"
    ARCHIVED = "archived"


LEAGUE_IDS: dict[str, str] = {
    "premier_league": "EPL",
    "la_liga": "LL",
    "serie_a": "SA",
    "bundensliga": "BL",
    "ligue_1": "L1",
    "mls": "MLS",
    "nfl": "NFL",
    "nba": "NBA",
    "mlb": "MLB",
    "nhl": "NHL",
}

POSITION_CODES: dict[str, str] = {
    "goalkeeper": "GK",
    "defender": "DEF",
    "midfielder": "MID",
    "forward": "FWD",
    "center_back": "CB",
    "left_back": "LB",
    "right_back": "RB",
    "center_mid": "CM",
    "attacking_mid": "AM",
    "defensive_mid": "DM",
    "center_forward": "CF",
    "left_wing": "LW",
    "right_wing": "RW",
    "striker": "ST",
}

DEFAULT_ROLLING_WINDOWS: list[int] = [3, 5, 10, 12]

ACUTE_WINDOW_DAYS: int = 7
CHRONIC_WINDOW_DAYS: int = 28
DANGER_ZONE_THRESHOLD: float = 1.5
