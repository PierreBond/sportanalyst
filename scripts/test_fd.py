import httpx

url = "https://www.football-data.co.uk/mmz4281/2627/E0.csv"
r = httpx.get(url, timeout=30, follow_redirects=True)
print(f"Status: {r.status_code}")
print(f"Final URL: {r.url}")
print(f"Content length: {len(r.content)}")
print(f"First 200 chars: {r.text[:200]}")
