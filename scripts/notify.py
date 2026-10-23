"""Push notification helper via ntfy.sh (free, no account needed).

Set NTFY_TOPIC (e.g. "sportanalyst-alerts") to enable; leave unset to make
every call a no-op. Use a unique topic name for privacy, subscribe to it from
the ntfy app.
"""
import os
import sys

try:
    import httpx
except ImportError:  # scripts may run outside the serving env
    httpx = None


def notify(title: str, message: str, priority: str = "default") -> bool:
    """Send a push notification. Returns False when disabled or failed."""
    topic = (os.environ.get("NTFY_TOPIC") or "").strip()
    if not topic or httpx is None:
        return False
    url = topic if topic.startswith("http") else f"https://ntfy.sh/{topic}"
    headers = {"Title": title, "Priority": priority, "Tags": "warning"}
    token = (os.environ.get("NTFY_TOKEN") or "").strip()
    if token:
        headers["Authorization"] = f"Bearer {token}"
    try:
        r = httpx.post(url, content=message, headers=headers, timeout=10)
        return r.status_code < 300
    except Exception as e:
        print(f"notify failed: {e}", file=sys.stderr)
        return False
