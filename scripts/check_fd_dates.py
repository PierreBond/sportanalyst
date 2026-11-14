import httpx
import pandas as pd
import io
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))
from pull_odds import canon

url = "https://football-data.co.uk/mmz4281/2627/E0.csv"
r = httpx.get(url, timeout=30)
df = pd.read_csv(io.BytesIO(r.content))

print("Premier League CSV date range:")
print(f"  {df['Date'].min()} to {df['Date'].max()}")
print(f"  Rows: {len(df)}")
