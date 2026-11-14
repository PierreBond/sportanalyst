import httpx
import json
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))
from pull_odds import canon

ODDS_API_KEY = "42f2603c056155e705e6849b0b2eb49d"

# Check what premier_league scores look like
url = f"https://api.the-odds-api.com/v4/sports/soccer_epl/scores/"
params = {"apiKey": ODDS_API_KEY}

r = httpx.get(url, params=params, timeout=30)
print(f"Status: {r.status_code}")
print(f"Remaining: {r.headers.get('x-requests-remaining', '?')}")

games = r.json()
print(f"Number of games: {len(games)}")

if games:
    print("\nSample game:")
    print(json.dumps(games[0], indent=2)[:1000])
