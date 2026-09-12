"""Fetch 2026 Brasileirao results from football-data.org, update DB, validate model."""
import json, os, re, sys
from pathlib import Path
import pandas as pd
import numpy as np
import joblib, httpx
from sqlalchemy import create_engine, text
from sklearn.preprocessing import LabelEncoder
from datetime import datetime, timezone

BASE = Path("C:\\Users\\DELL\\OneDrive\\Desktop\\sportanalyst")
MODEL_DIR = BASE / "models"

# Get key
env_path = BASE / ".env"
api_key = next((m.group(1) for line in env_path.read_text().splitlines() if (m:=re.match(r'^FOOTBALL_DATA_ORG_KEY=(.+)$', line.strip()))), None)
if not api_key: print("No key"); sys.exit(1)

print("Fetching 2026 Brasileirao matches from football-data.org...")
r = httpx.get("https://api.football-data.org/v4/competitions/BSA/matches?season=2026",
              headers={"X-Auth-Token": api_key}, timeout=30)
matches = r.json().get("matches", [])
finished = [m for m in matches if m["status"] == "FINISHED"]
print(f"  {len(finished)} finished matches")

engine = create_engine(os.environ["DATABASE_URL_SYNC"])

# Update DB with results
updated = 0
for m in finished:
    ext_id = f"footballdata_{m['id']}"
    score = m["score"]["fullTime"]
    hs, aws = score.get("home"), score.get("away")
    if hs is None or aws is None: continue
    with engine.connect() as conn:
        result = conn.execute(text("""
            UPDATE matches SET status='FT', home_score=:hs, away_score=:aws, updated_at=NOW()
            WHERE external_id=:eid AND (status IS NULL OR status='scheduled')
        """), {"hs": hs, "aws": aws, "eid": ext_id})
        conn.commit()
        if result.rowcount > 0: updated += 1

print(f"  Updated {updated} matches to FT status")

# Load 2026 FT matches from DB
df = pd.read_sql("""
    SELECT m.match_id::text, m.scheduled_at, m.home_score, m.away_score,
           ht.name AS home_team, at.name AS away_team, m.league, m.season,
           m.home_team_id, m.away_team_id
    FROM matches m JOIN teams ht ON m.home_team_id=ht.team_id JOIN teams at ON m.away_team_id=at.team_id
    WHERE m.status='FT' AND m.scheduled_at >= '2026-01-01'
    ORDER BY m.scheduled_at
""", engine)
engine.dispose()
print(f"Loaded {len(df)} 2026 FT matches from DB")

# Feature engineering
def team_games_df(df):
    home = df[["match_id","scheduled_at","home_team_id","home_score","away_score"]].copy()
    home.columns = ["match_id","scheduled_at","team_id","scored","conceded"]
    away = df[["match_id","scheduled_at","away_team_id","away_score","home_score"]].copy()
    away.columns = ["match_id","scheduled_at","team_id","scored","conceded"]
    all_g = pd.concat([home,away]).sort_values("scheduled_at").reset_index(drop=True)
    all_g["pts"] = (all_g["scored"]>all_g["conceded"]).astype(float)*3 + (all_g["scored"]==all_g["conceded"]).astype(float)
    return all_g

def add_rolling(all_g, df, prefix, window, game_side=None):
    g = all_g.copy()
    if game_side: g = g[g["game_side"]==game_side]
    for col, name in [("scored","gf_avg"),("conceded","ga_avg"),("pts","form")]:
        g[f"{name}_{window}"] = g.groupby("team_id")[col].transform(lambda x: x.shift(1).rolling(window, min_periods=1).mean())
    col_map = g.groupby("match_id").first().add_prefix(f"{prefix}_")
    for suffix in ["gf_avg","ga_avg","form"]:
        df[f"{prefix}_{suffix}_last{window}"] = df["match_id"].map(col_map[f"{prefix}_{suffix}_{window}"]).fillna(0)
    return df

df = df.sort_values("scheduled_at").reset_index(drop=True)
all_g = team_games_df(df)
n = len(df)
all_g["game_side"] = ["home"]*n + ["away"]*n
for w in [3,5,10]:
    df = add_rolling(all_g, df, "home", w)
    df = add_rolling(all_g, df, "away", w)
for name, cond in [("home_h","home"),("away_a","away")]:
    sub = all_g[all_g["game_side"]==cond].copy()
    for col, nm in [("scored","gf_avg"),("conceded","ga_avg"),("pts","form")]:
        g = sub.groupby("team_id")[col].transform(lambda x: x.shift(1).rolling(5, min_periods=1).mean())
        cm = sub.assign(**{f"{nm}_5": g}).groupby("match_id").first().add_prefix(f"{name}_")
        df[f"{name}_{nm}_last5"] = df["match_id"].map(cm[f"{name}_{nm}_5"]).fillna(0)
for side, tid_col in [("home","home_team_id"),("away","away_team_id")]:
    last_date = df.groupby(tid_col)["scheduled_at"].shift(1)
    df[f"{side}_days_rest"] = (df["scheduled_at"]-last_date).dt.days.fillna(7).clip(1,30)
league_stats = df.groupby("league")["home_score"].agg(["count","sum"]).join(df.groupby("league")["away_score"].agg("sum"))
league_stats["avg_total_goals"] = (league_stats["sum"]+league_stats["away_score"])/league_stats["count"].replace(0,np.nan)
df["league_avg_total_goals"] = df["league"].map(league_stats["avg_total_goals"].to_dict()).fillna(2.5)
h2h_rows = []
for _, row in df.iterrows():
    h2h = df[((df["home_team_id"]==row["home_team_id"])&(df["away_team_id"]==row["away_team_id"])|
             (df["home_team_id"]==row["away_team_id"])&(df["away_team_id"]==row["home_team_id"]))]
    h2h = h2h[h2h["scheduled_at"]<row["scheduled_at"]].tail(5)
    if len(h2h)>0:
        hg = h2h.apply(lambda r: r["home_score"] if r["home_team_id"]==row["home_team_id"] else r["away_score"], axis=1)
        ag = h2h.apply(lambda r: r["away_score"] if r["home_team_id"]==row["home_team_id"] else r["home_score"], axis=1)
        h2h_rows.append({"match_id":row["match_id"],"h2h_home_gf_avg":hg.mean(),"h2h_away_gf_avg":ag.mean(),"h2h_home_wins":(hg>ag).mean()})
    else:
        h2h_rows.append({"match_id":row["match_id"],"h2h_home_gf_avg":0,"h2h_away_gf_avg":0,"h2h_home_wins":0.5})
h2h_df = pd.DataFrame(h2h_rows).set_index("match_id")
for c in h2h_df.columns: df[c] = df["match_id"].map(h2h_df[c]).fillna(0)
elo, elo_rows = {}, []
for _, row in df.iterrows():
    ht, at = row["home_team_id"], row["away_team_id"]
    elo_h = elo.get(ht,1500)+100; elo_a = elo.get(at,1500)
    s_h = 1 if row["home_score"]>row["away_score"] else (0.5 if row["home_score"]==row["away_score"] else 0)
    e_h = 1/(1+10**((elo_a-elo_h)/400))
    elo[ht] = elo.get(ht,1500)+32*(s_h-e_h)
    elo[at] = elo.get(at,1500)+32*((1-s_h)-(1-e_h))
    elo_rows.append({"match_id":row["match_id"],"home_elo":elo_h,"away_elo":elo_a,"elo_diff":elo_h-elo_a})
elo_df = pd.DataFrame(elo_rows).set_index("match_id")
for c in elo_df.columns: df[c] = df["match_id"].map(elo_df[c]).fillna(0)
df["target"] = df.apply(lambda r: 0 if r["home_score"]>r["away_score"] else (1 if r["home_score"]==r["away_score"] else 2), axis=1)
df = df.dropna(subset=["target"])

print(f"Features built: {len(df)} matches")

# Encode using saved model
meta = json.load(open(MODEL_DIR/"predictor_metadata.json"))
team_classes, league_classes = meta["team_classes"], meta["league_classes"]
le_team = LabelEncoder(); le_team.classes_ = np.array(team_classes)
le_league = LabelEncoder(); le_league.classes_ = np.array(league_classes)
FEATURES = [
    "home_team_encoded","away_team_encoded","league_encoded",
    "home_gf_avg_last3","home_ga_avg_last3","home_form_last3",
    "home_gf_avg_last5","home_ga_avg_last5","home_form_last5",
    "home_gf_avg_last10","home_ga_avg_last10","home_form_last10",
    "away_gf_avg_last3","away_ga_avg_last3","away_form_last3",
    "away_gf_avg_last5","away_ga_avg_last5","away_form_last5",
    "away_gf_avg_last10","away_ga_avg_last10","away_form_last10",
    "home_h_gf_avg_last5","home_h_ga_avg_last5","home_h_form_last5",
    "away_a_gf_avg_last5","away_a_ga_avg_last5","away_a_form_last5",
    "home_days_rest","away_days_rest","league_avg_total_goals",
    "h2h_home_gf_avg","h2h_away_gf_avg","h2h_home_wins","season",
    "home_elo","away_elo","elo_diff",
]
df["home_team_enc"] = df["home_team"].map(lambda x: le_team.transform([x])[0] if x in team_classes else 0)
df["away_team_enc"] = df["away_team"].map(lambda x: le_team.transform([x])[0] if x in team_classes else 0)
df["league_enc"] = df["league"].map(lambda x: le_league.transform([x])[0] if x in league_classes else 0)

X = pd.DataFrame({
    "home_team_encoded": df["home_team_enc"], "away_team_encoded": df["away_team_enc"],
    "league_encoded": df["league_enc"],
    **{f: df[f].astype(float) for f in FEATURES if f not in ["home_team_encoded","away_team_encoded","league_encoded"]},
})
X = X[FEATURES]
y = df["target"]

# Predict
model_xgb = joblib.load(MODEL_DIR/"predictor.joblib")
y_prob = model_xgb.predict_proba(X)
y_pred = y_prob.argmax(axis=1)
acc = (y_pred==y).mean()
from sklearn.metrics import confusion_matrix
cm = confusion_matrix(y, y_pred)
brier = np.mean([(y==i).astype(int)-y_prob[:,i] for i in range(3)])

labels = {0:"H",1:"D",2:"A"}
df["pred"] = y_pred; df["correct"] = (y_pred==y)
df["actual_lbl"] = df["target"].map(labels); df["pred_lbl"] = df["pred"].map(labels)
df["h_prob"] = [round(p[0],4) for p in y_prob]
df["d_prob"] = [round(p[1],4) for p in y_prob]
df["a_prob"] = [round(p[2],4) for p in y_prob]
df["conf"] = df[["h_prob","d_prob","a_prob"]].max(axis=1)

print(f"\n=== 2026 Season Validation ===")
print(f"Matches: {len(df)}")
print(f"Accuracy: {acc:.4f} ({y_pred[y_pred==y].shape[0]}/{len(y)})")
print(f"Confusion matrix:\n{cm}")

# Save report
now = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
correct_top = df[df["correct"]].sort_values("conf",ascending=False)
wrong_top = df[~df["correct"]].sort_values("conf",ascending=False)

md = f"""# Model Validation Report — 2026 Season (Brasileirão Série A)

Generated: {now}
Model: Tuned XGBoost (n_estimators=400, max_depth=4, lr=0.02)
Training data: 8,538 matches (2022 — 2025-06-01)
Validation data: {len(df)} matches (2026 Brasileirão, pulled from football-data.org)

---

## Summary

**Accuracy: {acc:.4f}** ({y_pred[y_pred==y].shape[0]}/{len(y)} correct)

### Confusion Matrix

| | Pred H | Pred D | Pred A |
|---|---|---|---|
| Actual H | {cm[0,0]} | {cm[0,1]} | {cm[0,2]} |
| Actual D | {cm[1,0]} | {cm[1,1]} | {cm[1,2]} |
| Actual A | {cm[2,0]} | {cm[2,1]} | {cm[2,2]} |

---

## Most Confident Correct Predictions (top 20)

| Home | Away | Score | Pred | H | D | A | Conf |
|------|------|-------|------|---|---|---|---|
"""
for _, r in correct_top.head(20).iterrows():
    md += f"| {r['home_team'][:22]} | {r['away_team'][:22]} | {int(r['home_score'])}-{int(r['away_score'])} | {r['pred_lbl']} | {r['h_prob']:.3f} | {r['d_prob']:.3f} | {r['a_prob']:.3f} | {r['conf']:.3f} |\n"

md += f"""
---

## Most Confident Wrong Predictions (top 20)

| Home | Away | Score | Pred | Actual | H | D | A | Conf |
|------|------|-------|------|--------|---|---|---|---|
"""
for _, r in wrong_top.head(20).iterrows():
    md += f"| {r['home_team'][:22]} | {r['away_team'][:22]} | {int(r['home_score'])}-{int(r['away_score'])} | {r['pred_lbl']} | {r['actual_lbl']} | {r['h_prob']:.3f} | {r['d_prob']:.3f} | {r['a_prob']:.3f} | {r['conf']:.3f} |\n"

md += f"""
---

## All Matches ({len(df)})

| # | Date | Home | Away | Score | Actual | Pred | H | D | A | ✓ |
|---|---|---|---|---|---|---|---|---|---|---|
"""
for i, (_, r) in enumerate(df.sort_values("scheduled_at").iterrows()):
    dt = pd.Timestamp(r["scheduled_at"]).strftime("%Y-%m-%d")
    md += f"| {i+1} | {dt} | {r['home_team'][:20]} | {r['away_team'][:20]} | {int(r['home_score'])}-{int(r['away_score'])} | {r['actual_lbl']} | {r['pred_lbl']} | {r['h_prob']:.3f} | {r['d_prob']:.3f} | {r['a_prob']:.3f} | {'✓' if r['correct'] else '✗'} |\n"

out_path = BASE / "validation_report_2026.md"
out_path.write_text(md, encoding="utf-8")
print(f"\nReport saved to {out_path}")
