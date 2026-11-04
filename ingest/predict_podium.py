"""UC1 · Podium prediction: trains on GOLD.UC1_PODIUM_FEATURES, scores the next race,
writes GOLD.UC1_PODIUM_PREDICTIONS and GOLD.UC1_MODEL_BACKTEST.

Model: a LOGISTIC REGRESSION (simple and explainable: one weight per feature), trained on every finished
race with the most recent seasons weighing most. Inputs of the next race = the latest information only:
form over the last 5 races, team points over the last 5 races, history at this circuit, the qualifying
grid (as soon as it exists), practice pace of the weekend, rain forecast.
Acceptance test (UC1): on last season, the model must find more podium finishers than the naive
baseline "the top 3 on the grid finish on the podium".

  python predict_podium.py --run-date 2026-11-07
Idempotent: the predictions of a race are replaced, never appended (DELETE + INSERT in one transaction).
"""
import argparse
import datetime as dt

import pandas as pd
from sklearn.impute import SimpleImputer
from sklearn.linear_model import LogisticRegression
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import StandardScaler

MODEL_VERSION = "logreg-recency-v1"
FEATURES = ["grid", "quali_gap_pct", "driver_avg_finish_5", "driver_avg_finish_circuit",
            "team_avg_points_5", "practice_gap_pct", "is_wet_race"]


def prepare(df):
    X = df[FEATURES].astype(float)
    # before qualifying the grid is unknown: use the driver's recent average finish instead
    X["grid"] = X["grid"].where(X["grid"] > 0).fillna(X["driver_avg_finish_5"])
    X["is_wet_race"] = X["is_wet_race"].fillna(0)
    return X


def make_model():
    # keep_empty_features: a feature with no value yet (e.g. new circuit) is kept, so weights stay aligned
    return make_pipeline(SimpleImputer(strategy="median", keep_empty_features=True), StandardScaler(),
                         LogisticRegression(max_iter=1000))


def fit(train):
    """MOST RECENT DATA COUNTS MOST: each season back weighs half as much as the next one
    (current season = 1, last season = 0.5, two seasons ago = 0.25...). Cars change every year,
    and completely in 2026 with the new rules: recent races say more about the next one."""
    weight = 0.5 ** (train["season"].max() - train["season"])
    return make_model().fit(prepare(train), train["is_podium"].astype(int),
                            logisticregression__sample_weight=weight)


def podium_hits(scored, score_col):
    """Per race: how many of the 3 drivers ranked best by score_col really finished on the podium."""
    top3 = scored.sort_values(score_col, ascending=False).groupby("race_id").head(3)
    return top3.groupby("race_id")["is_podium"].sum()


def backtest(df, season):
    """Train on the seasons before `season`, test on `season`; compare with the grid baseline."""
    past = df[df["is_podium"].notna()]
    train, test = past[past["season"] < season], past[past["season"] == season].copy()
    if train.empty or test.empty:
        return None
    model = fit(train)
    test["p_podium"] = model.predict_proba(prepare(test))[:, 1]
    test["grid_score"] = -test["grid"].where(test["grid"] > 0, 99)      # pole = best score
    model_hits, grid_hits = podium_hits(test, "p_podium"), podium_hits(test, "grid_score")
    return {"season": season, "races": int(test["race_id"].nunique()),
            "model_hit_rate": round(float(model_hits.mean()) / 3, 3), "grid_hit_rate": round(float(grid_hits.mean()) / 3, 3),
            "accepted": bool(model_hits.mean() > grid_hits.mean())}


def predict_next(df):
    past, nxt = df[df["is_podium"].notna()], df[df["is_next_race"].astype(bool)].copy()
    model = fit(past)                    # every finished race up to the last one, recent ones weigh most
    nxt["p_podium"] = model.predict_proba(prepare(nxt))[:, 1].round(3)
    nxt["predicted_rank"] = nxt["p_podium"].rank(ascending=False, method="first").astype(int)
    weights = {f: round(float(w), 2) for f, w in zip(FEATURES, model[-1].coef_[0])}
    return nxt.sort_values("predicted_rank"), weights


def main():
    from common import RUN_ID, connect
    ap = argparse.ArgumentParser()
    ap.add_argument("--run-date", default=str(dt.date.today()))
    a = ap.parse_args()
    con = connect()
    cur = con.cursor()
    try:
        cur.execute("SELECT * FROM GOLD.UC1_PODIUM_FEATURES")
        df = cur.fetch_pandas_all()
        df.columns = [c.lower() for c in df.columns]
        df[FEATURES + ["season"]] = df[FEATURES + ["season"]].astype(float)   # Snowflake NUMBER -> float
        # Backtest on the CURRENT season's finished races (2026: new cars, the most relevant test),
        # trained on everything before; and on last season (2025) for comparison.
        year = dt.date.fromisoformat(a.run_date).year
        backtests = [b for b in (backtest(df, year - 1), backtest(df, year)) if b]
        for b in backtests:
            print(f"Backtest {b['season']}: {b}")
        preds, weights = predict_next(df)
        print(f"Model weights (standardised): {weights}")
        if preds.empty:
            print("No next race in the calendar: nothing to score")
            return
        race_id = preds["race_id"].iloc[0]
        print(preds[["predicted_rank", "driver_ref", "grid", "p_podium"]].head(10).to_string(index=False))

        cur.execute("""CREATE TABLE IF NOT EXISTS GOLD.UC1_PODIUM_PREDICTIONS (RACE_ID VARCHAR, DRIVER_REF VARCHAR,
                       PREDICTED_RANK INT, P_PODIUM FLOAT, GRID_KNOWN BOOLEAN, MODEL_VERSION VARCHAR,
                       SCORED_AT TIMESTAMP_TZ, RUN_ID VARCHAR)""")
        cur.execute("BEGIN")
        cur.execute("DELETE FROM GOLD.UC1_PODIUM_PREDICTIONS WHERE RACE_ID = %s", (race_id,))
        cur.executemany("""INSERT INTO GOLD.UC1_PODIUM_PREDICTIONS
                           VALUES (%s, %s, %s, %s, %s, %s, CURRENT_TIMESTAMP(), %s)""",
                        [(race_id, r.driver_ref, int(r.predicted_rank), float(r.p_podium), bool(r.grid > 0),
                          MODEL_VERSION, RUN_ID) for r in preds.itertuples()])
        cur.execute("COMMIT")

        cur.execute("""CREATE TABLE IF NOT EXISTS GOLD.UC1_MODEL_BACKTEST (SEASON INT, RACES INT,
                       MODEL_HIT_RATE FLOAT, GRID_HIT_RATE FLOAT, ACCEPTED BOOLEAN, MODEL_VERSION VARCHAR,
                       SCORED_AT TIMESTAMP_TZ)""")
        for bt in backtests:
            cur.execute("""MERGE INTO GOLD.UC1_MODEL_BACKTEST t
                           USING (SELECT %s SEASON, %s RACES, %s MH, %s GH, %s ACC, %s MV) s
                           ON t.SEASON = s.SEASON AND t.MODEL_VERSION = s.MV
                           WHEN MATCHED THEN UPDATE SET RACES = s.RACES, MODEL_HIT_RATE = s.MH,
                                GRID_HIT_RATE = s.GH, ACCEPTED = s.ACC, SCORED_AT = CURRENT_TIMESTAMP()
                           WHEN NOT MATCHED THEN INSERT VALUES (s.SEASON, s.RACES, s.MH, s.GH, s.ACC, s.MV,
                                CURRENT_TIMESTAMP())""",
                        (bt["season"], bt["races"], bt["model_hit_rate"], bt["grid_hit_rate"], bt["accepted"],
                         MODEL_VERSION))
        print(f"{len(preds)} predictions written for {race_id} (run {RUN_ID})")
    finally:
        cur.close()
        con.close()


if __name__ == "__main__":
    main()
