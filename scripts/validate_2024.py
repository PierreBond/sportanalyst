"""Validate model against 2024 FT season — predictions vs actual results."""
import json, os, warnings
from pathlib import Path
import pandas as pd
import numpy as np
import joblib
from sqlalchemy import create_engine
from sklearn.preprocessing import LabelEncoder
from sklearn.metrics import brier_score_loss, confusion_matrix, roc_auc_score
from sklearn.linear_model import PoissonRegressor
from scipy.stats import poisson

warnings.filterwarnings("ignore")
BASE = Path(__file__).resolve().parent.parent
MODEL_DIR = BASE / "models"

engine = create_engine(os.environ["DATABASE_URL_SYNC"])
print("Loading 2024 FT matches...")
df = pd.read_sql("""
    SELECT m.match_id, m.league, m.season, m.scheduled_at, m.home_score, m.away_score,
           ht.name AS home_team, at.name AS away_team, m.home_team_id, m.away_team_id
    FROM matches m JOIN teams ht ON ht.team_id = m.home_team_id JOIN teams at ON at.team_id = m.away_team_id
    WHERE m.home_score IS NOT NULL AND m.away_score IS NOT NULL AND m.status = 'FT'
      AND m.scheduled_at >= '2024-01-01' AND m.scheduled_at < '2025-01-01'
    ORDER BY m.scheduled_at
""", engine)
engine.dispose()
print(f"Loaded {len(df)} matches")

# ---- Feature engineering (identical to train_model.py) ----
def team_games_df(df):
    home = df[["match_id","scheduled_at","home_team_id","home_score","away_score"]].copy()
    home.columns = ["match_id","scheduled_at","team_id","scored","conceded"]
    away = df[["match_id","scheduled_at","away_team_id","away_score","home_score"]].copy()
    away.columns = ["match_id","scheduled_at","team_id","scored","conceded"]
    all_g = pd.concat([home,away]).sort_values("scheduled_at").reset_index(drop=True)
    all_g["pts"] = (all_g["scored"] > all_g["conceded"]).astype(float)*3
    all_g["pts"] += (all_g["scored"] == all_g["conceded"]).astype(float)
    return all_g

def add_rolling(all_g, df, prefix, window, game_side=None):
    g = all_g.copy()
    if game_side:
        g = g[g["game_side"]==game_side] if "game_side" in g.columns else g
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
home_only = all_g[all_g["game_side"]=="home"].copy()
df = add_rolling(home_only, df, "home_h", 5)
away_only = all_g[all_g["game_side"]=="away"].copy()
df = add_rolling(away_only, df, "away_a", 5)

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
for c in h2h_df.columns:
    df[c] = df["match_id"].map(h2h_df[c]).fillna(0)

elo, elo_rows = {}, []
for _, row in df.iterrows():
    ht, at = row["home_team_id"], row["away_team_id"]
    elo_h = elo.get(ht,1500)+100
    elo_a = elo.get(at,1500)
    e_h = 1/(1+10**((elo_a-elo_h)/400))
    s_h = 1 if row["home_score"]>row["away_score"] else (0.5 if row["home_score"]==row["away_score"] else 0)
    elo[ht] = elo.get(ht,1500)+32*(s_h-e_h)
    elo[at] = elo.get(at,1500)+32*((1-s_h)-(1-e_h))
    elo_rows.append({"match_id":row["match_id"],"home_elo":elo_h,"away_elo":elo_a,"elo_diff":elo_h-elo_a})
elo_df = pd.DataFrame(elo_rows).set_index("match_id")
for c in elo_df.columns:
    df[c] = df["match_id"].map(elo_df[c]).fillna(0)

df["target"] = df.apply(lambda r: 0 if r["home_score"]>r["away_score"] else (1 if r["home_score"]==r["away_score"] else 2), axis=1)
df = df.dropna(subset=["target"])
print(f"Features built: {len(df)} matches")

# ---- Encode using saved model's classes ----
meta = json.load(open(MODEL_DIR/"predictor_metadata.json"))
team_classes = meta["team_classes"]
league_classes = meta["league_classes"]
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

# ---- Load models ----
print("Loading models...")
model_xgb = joblib.load(MODEL_DIR/"predictor.joblib")
poisson_models = joblib.load(MODEL_DIR/"poisson.joblib")
poisson_home = poisson_models["home"]
poisson_away = poisson_models["away"]

# ---- Predict ----
print("Running predictions...")
y_prob_xgb = model_xgb.predict_proba(X)
lambda_h = poisson_home.predict(X)
lambda_a = poisson_away.predict(X)

def pp(lh, la, mg=8):
    ph = poisson.pmf(np.arange(mg+1), lh); pa = poisson.pmf(np.arange(mg+1), la)
    phome = sum(ph[i]*sum(pa[:i]) for i in range(mg+1))
    paway = sum(pa[i]*sum(ph[:i]) for i in range(mg+1))
    return phome, paway, 1-phome-paway

y_prob_poisson = np.array([pp(lh, la) for lh, la in zip(lambda_h, lambda_a)])
y_prob_ens = (y_prob_xgb + y_prob_poisson) / 2

# ---- Evaluate ----
results = []
for nm, yp in [("XGBoost",y_prob_xgb),("Poisson",y_prob_poisson),("Ensemble",y_prob_ens)]:
    yp_ = yp.argmax(axis=1)
    acc = (yp_==y).mean()
    brier = np.mean([brier_score_loss((y==i).astype(int),yp[:,i]) for i in range(3)])
    try:
        roc_h = roc_auc_score((y==0).astype(int),yp[:,0])
        roc_d = roc_auc_score((y==1).astype(int),yp[:,1])
        roc_a = roc_auc_score((y==2).astype(int),yp[:,2])
    except: roc_h=roc_d=roc_a=0
    results.append((nm,acc,brier,roc_h,roc_d,roc_a))
    print(f"  {nm:10s}  acc={acc:.4f}  brier={brier:.4f}")

# ---- Build per-match table ----
df["xgb_h"] = [round(p[0],4) for p in y_prob_xgb]
df["xgb_d"] = [round(p[1],4) for p in y_prob_xgb]
df["xgb_a"] = [round(p[2],4) for p in y_prob_xgb]
df["ens_h"] = [round(p[0],4) for p in y_prob_ens]
df["ens_d"] = [round(p[1],4) for p in y_prob_ens]
df["ens_a"] = [round(p[2],4) for p in y_prob_ens]
df["pred"] = y_prob_ens.argmax(axis=1)
df["correct"] = (df["pred"]==df["target"])
labels = {0:"H",1:"D",2:"A"}
df["actual"] = df["target"].map(labels)
df["predicted"] = df["pred"].map(labels)
df["confidence"] = df[["ens_h","ens_d","ens_a"]].max(axis=1)

cm_xgb = confusion_matrix(y, y_prob_xgb.argmax(axis=1))
cm_ens = confusion_matrix(y, y_prob_ens.argmax(axis=1))

# League breakdown
league_accs = []
for league in df["league"].unique():
    mask = df["league"]==league
    acc_l = (y_prob_xgb[mask].argmax(axis=1)==y[mask]).mean()
    league_accs.append((league, mask.sum(), acc_l))
league_accs.sort(key=lambda x: x[2], reverse=True)

# ---- Generate markdown ----
now = pd.Timestamp.now(tz="UTC").strftime("%Y-%m-%d %H:%M UTC")
correct_top = df[df["correct"]].sort_values("confidence",ascending=False)
wrong_top = df[~df["correct"]].sort_values("confidence",ascending=False)

md = f"""# Model Validation Report — 2024 Season

Generated: {now}
Model: Tuned XGBoost (n_estimators=400, max_depth=4, lr=0.02) + PoissonRegressor ensemble
Training data: 8,538 matches (2022 — 2025-06-01)
Validation data: {len(df)} matches (2024 season)

---

## Summary Metrics

| Model | Accuracy | Brier Avg | AUC (H) | AUC (D) | AUC (A) |
|-------|----------|-----------|---------|---------|---------|
"""
for nm, acc, brier, roc_h, roc_d, roc_a in results:
    md += f"| {nm:8s} | {acc:.4f} | {brier:.4f} | {roc_h:.4f} | {roc_d:.4f} | {roc_a:.4f} |\n"

md += f"""
### Confusion Matrix — XGBoost

| | Pred H | Pred D | Pred A |
|---|---|---|---|
| Actual H | {cm_xgb[0,0]} | {cm_xgb[0,1]} | {cm_xgb[0,2]} |
| Actual D | {cm_xgb[1,0]} | {cm_xgb[1,1]} | {cm_xgb[1,2]} |
| Actual A | {cm_xgb[2,0]} | {cm_xgb[2,1]} | {cm_xgb[2,2]} |

### Confusion Matrix — Ensemble

| | Pred H | Pred D | Pred A |
|---|---|---|---|
| Actual H | {cm_ens[0,0]} | {cm_ens[0,1]} | {cm_ens[0,2]} |
| Actual D | {cm_ens[1,0]} | {cm_ens[1,1]} | {cm_ens[1,2]} |
| Actual A | {cm_ens[2,0]} | {cm_ens[2,1]} | {cm_ens[2,2]} |

---

## League Breakdown (XGBoost)

| League | Matches | Accuracy |
|--------|---------|----------|
"""
for l, c, a in league_accs:
    md += f"| {l:20s} | {c:4d} | {a:.3f} |\n"

md += f"""
---

## Most Confident Correct Predictions (20)

| Home | Away | Score | Pred | H | D | A | Conf |
|------|------|-------|------|---|---|---|---|
"""
for _, r in correct_top.head(20).iterrows():
    md += f"| {r['home_team'][:22]} | {r['away_team'][:22]} | {int(r['home_score'])}-{int(r['away_score'])} | {r['predicted']} | {r['ens_h']:.3f} | {r['ens_d']:.3f} | {r['ens_a']:.3f} | {r['confidence']:.3f} |\n"

md += f"""
---

## Most Confident Wrong Predictions (20)

| Home | Away | Score | Pred | Actual | H | D | A | Conf |
|------|------|-------|------|--------|---|---|---|---|
"""
for _, r in wrong_top.head(20).iterrows():
    md += f"| {r['home_team'][:22]} | {r['away_team'][:22]} | {int(r['home_score'])}-{int(r['away_score'])} | {r['predicted']} | {r['actual']} | {r['ens_h']:.3f} | {r['ens_d']:.3f} | {r['ens_a']:.3f} | {r['confidence']:.3f} |\n"

md += f"""
---

## All Matches ({len(df)})

| # | Date | Home | Away | Score | Actual | Pred | H | D | A | ✓ |
|---|---|---|---|---|---|---|---|---|---|---|
"""
for i, (_, r) in enumerate(df.iterrows()):
    dt = pd.Timestamp(r["scheduled_at"]).strftime("%Y-%m-%d")
    md += f"| {i+1} | {dt} | {r['home_team'][:20]} | {r['away_team'][:20]} | {int(r['home_score'])}-{int(r['away_score'])} | {r['actual']} | {r['predicted']} | {r['ens_h']:.3f} | {r['ens_d']:.3f} | {r['ens_a']:.3f} | {'✓' if r['correct'] else '✗'} |\n"

out_path = BASE / "validation_report_2024.md"
out_path.write_text(md, encoding="utf-8")
print(f"\nReport saved to {out_path} ({out_path.stat().st_size} bytes)")
