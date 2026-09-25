"""Settlement check: model vs market (implied odds) vs actual outcomes.

Part 1 — market benchmark: all FT matches with odds, vig-normalized implied
         probabilities vs actual outcome (the number the model must beat).
Part 2 — model head-to-head: stored predictions for finished matches vs
         outcome and vs implied probabilities on the same match.
"""
import os

import numpy as np
import pandas as pd
from sqlalchemy import create_engine, text


def brier(probs: pd.DataFrame, y: pd.Series) -> float:
    p = probs.to_numpy(dtype=float)
    onehot = np.eye(3)[y.to_numpy(dtype=int)]
    return float(((p - onehot) ** 2).sum(axis=1).mean() / 3)


def implied_from_odds(h: float, d: float, a: float) -> tuple[float, float, float] | None:
    if min(h, d, a) <= 1.0:
        return None
    inv = (1 / h, 1 / d, 1 / a)
    s = sum(inv)
    return (inv[0] / s, inv[1] / s, inv[2] / s)


def main():
    engine = create_engine(os.environ["DATABASE_URL_SYNC"])

    odds = pd.read_sql(text("""
        SELECT DISTINCT ON (m.match_id) m.match_id::text, m.home_score, m.away_score,
               o.home_odds, o.draw_odds, o.away_odds
        FROM matches m
        JOIN odds_snapshots o ON o.match_id = m.match_id AND o.market_type = 'h2h'
        WHERE m.status = 'FT' AND m.home_score IS NOT NULL AND o.home_odds IS NOT NULL
        ORDER BY m.match_id, (o.sportsbook = 'Pinnacle') DESC, o.captured_at DESC
    """), engine)

    y = (odds.home_score == odds.away_score).astype(int) \
        + (odds.home_score < odds.away_score).astype(int) * 2  # 0=home, 1=draw, 2=away

    rows = []
    for (_, r), outcome in zip(odds.iterrows(), y):
        imp = implied_from_odds(float(r.home_odds), float(r.draw_odds), float(r.away_odds))
        if imp:
            rows.append((r.match_id, *imp, int(outcome)))
    mkt = pd.DataFrame(rows, columns=["match_id", "h", "d", "a", "y"])
    if len(mkt):
        mkt_acc = float((mkt[["h", "d", "a"]].values.argmax(axis=1) == mkt.y).mean())
        mkt_brier = brier(mkt[["h", "d", "a"]], mkt.y)
        print("=== Market benchmark (latest odds, FT) ===")
        print(f"n={len(mkt)}  implied Brier={mkt_brier:.4f}  favorite-pick accuracy={mkt_acc:.4f}")
    else:
        print("Market benchmark: no FT matches with odds")

    preds = pd.read_sql(text("""
        SELECT p.match_id::text, p.home_win_prob, p.draw_prob, p.away_win_prob,
               m.home_score, m.away_score
        FROM predictions p JOIN matches m ON m.match_id = p.match_id
        WHERE m.status = 'FT' AND m.home_score IS NOT NULL
    """), engine)
    engine.dispose()
    print("\n=== Model vs market (stored predictions, FT) ===")
    if len(preds) == 0:
        print("n=0 — no finished matches carry stored predictions yet (grows daily)")
        return
    y2 = (preds.home_score < preds.away_score).astype(int) * 2 \
        + (preds.home_score == preds.away_score).astype(int)
    mp = preds[["home_win_prob", "draw_prob", "away_win_prob"]].astype(float)
    mp.columns = ["h", "d", "a"]
    model_acc = float((mp.values.argmax(axis=1) == y2).mean())
    model_brier = brier(mp, y2)
    line = f"n={len(preds)}  model Brier={model_brier:.4f}  model accuracy={model_acc:.4f}"
    sub = mkt[mkt.match_id.isin(preds.match_id)]
    if len(sub):
        sub_acc = float((sub[["h", "d", "a"]].values.argmax(axis=1) == sub.y).mean())
        sub_brier = brier(sub[["h", "d", "a"]], sub.y)
        line += f"  | same matches: market Brier={sub_brier:.4f}  market acc={sub_acc:.4f}"
    print(line)


if __name__ == "__main__":
    main()
