"""Backtest the value-bet rule (edge >= 3%, quarter-Kelly stakes) on the test season.

Uses the SERVED v3.3 XGBoost model and the production BettingEngine rules.
Bets rated edge = model_prob - 1/odds, exactly as in services/model_serving.
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "libs"))
sys.path.insert(0, str(Path(__file__).resolve().parent))

from backtest_markets import build_test_frame
from services.model_serving.src.betting import BettingEngine, cap_slate
import joblib
from collections import defaultdict


def main():
    df, X, _train_mask, test_mask = build_test_frame()
    tdf = df.loc[test_mask].reset_index(drop=True)
    Xt = X.loc[test_mask].reset_index(drop=True)

    model = joblib.load(Path(__file__).resolve().parent.parent / "models" / "predictor.joblib")
    probs = model.predict_proba(Xt)

    engine = BettingEngine()
    sel_to_col = {"home_win": 0, "draw": 1, "away_win": 2}
    odds_cols = {"home_win": "home_odds", "draw": "draw_odds", "away_win": "away_odds"}

    by_day: dict[str, list] = defaultdict(list)
    bets = []
    for i, row in tdf.iterrows():
        p = {"home_win": probs[i, 0], "draw": probs[i, 1], "away_win": probs[i, 2]}
        odds = {k: float(row[c]) for k, c in odds_cols.items()}
        if any(o <= 1.0 for o in odds.values()):
            continue
        found = engine.evaluate_bets(str(row["match_id"]), p, odds, sportsbook="pinnacle-backtest")
        for b in found:
            outcome = b.selection
            hs, as_ = row["home_score"], row["away_score"]
            actual = 0 if hs > as_ else (1 if hs == as_ else 2)
            won = actual == sel_to_col[outcome]
            kelly = min(b.stake, 5.0) / 100.0  # b.stake is kelly% capped at 5 (percent)
            by_day[str(row["scheduled_at"])[:10]].append({
                "match_id": b.match_id, "selection": outcome, "odds": b.odds,
                "edge": b.expected_value, "won": won,
                "pnl_flat": (b.odds - 1.0) if won else -1.0,
                "stake_pct": kelly,
                "pnl_kelly": kelly * (b.odds - 1.0) if won else -kelly,
            })

    for slate in by_day.values():
        bets.extend(cap_slate(slate))

    if not bets:
        print("No value bets found in test season.")
        return

    bdf = __import__("pandas").DataFrame(bets)
    n = len(bdf)
    hit = float(bdf["won"].mean())
    roi_flat = float(bdf["pnl_flat"].sum() / n)
    roi_kelly = float(bdf["pnl_kelly"].sum())
    exp_roi_per_bet = float(bdf.apply(lambda r: r["edge"], axis=1).mean())

    print(f"Test season value-bet backtest ({n} bets)")
    print(f"Selection breakdown: {bdf['selection'].value_counts().to_dict()}")
    print(f"Hit rate: {hit:.4f}")
    print(f"Flat 1-unit ROI per bet: {roi_flat:+.4f} (total {bdf['pnl_flat'].sum():+.1f} units)")
    print(f"Quarter-Kelly bankroll return: {roi_kelly:+.4f} (bankroll units)")
    print(f"Avg edge per bet (model-claimed): {exp_roi_per_bet:+.4f}")
    print(f"Realized vs claimed: {'below' if roi_flat < exp_roi_per_bet else 'above'}")

    print("\nBy selection:")
    for sel, g in bdf.groupby("selection"):
        print(f"  {sel}: n={len(g)} hit={g['won'].mean():.3f} flat_roi={(g['pnl_flat'].sum() / len(g)):+.3f}")

    # calibration sanity: average actual outcome prob among bets
    print(f"Avg decimal odds: {bdf['odds'].mean():.2f}; implied bookmaker prob: {(1/bdf['odds']).mean():.3f}; model prob: {float((bdf['edge'] + (1/bdf['odds'])).mean()):.3f}")


if __name__ == "__main__":
    main()
