from .base_adapter import BaseAdapter
from .sportsdataio import SportsDataIOAdapter
from .api_sports import APISportsAdapter
from .football_data_org import FootballDataOrgAdapter
from .thesportsdb import TheSportsDBAdapter
from .catapult import CatapultAdapter
from .whoop import WhoopAdapter

from sports_common.config import settings


def create_sports_data_adapter() -> BaseAdapter:
    """Create the primary sports data adapter from env-backed settings.

    Selection rules:
    - If ``ODDS_SOURCE`` is ``api_sports`` (or empty), use APISportsAdapter.
    - If ``ODDS_SOURCE`` is ``sportsdataio``, use SportsDataIOAdapter.
    - For unsupported providers, fall back to APISportsAdapter.
    """
    source = (settings.odds_source or "api_sports").strip().lower()
    if source in {"thesportsdb", "the_sportsdb"}:
        return TheSportsDBAdapter(settings.thesportsdb_key)
    if source in {"football_data_org", "football-data", "football-data-org"}:
        return FootballDataOrgAdapter(settings.football_data_org_key)
    if source == "sportsdataio":
        return SportsDataIOAdapter(settings.sportsdataio_api_key)
    return APISportsAdapter(settings.api_sports_key)


def create_biometric_adapter(provider: str = "whoop") -> BaseAdapter:
    """Create a biometric adapter for the requested provider."""
    provider_name = (provider or "whoop").strip().lower()
    if provider_name == "catapult":
        return CatapultAdapter(
            api_key=settings.catapult_api_key,
            base_url=settings.catapult_base_url,
        )
    return WhoopAdapter(
        client_id=settings.whoop_client_id,
        client_secret=settings.whoop_client_secret,
    )

__all__ = [
    "BaseAdapter",
    "SportsDataIOAdapter",
    "APISportsAdapter",
    "FootballDataOrgAdapter",
    "TheSportsDBAdapter",
    "CatapultAdapter",
    "WhoopAdapter",
    "create_sports_data_adapter",
    "create_biometric_adapter",
]
