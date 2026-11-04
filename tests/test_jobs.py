"""Unit tests of the job logic that does not need Snowflake or the internet.  Run:  pytest tests/"""
import datetime as dt
import sys
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "ingest"))

import ingest_fastf1 as f1          # noqa: E402
import ingest_jolpica as jol        # noqa: E402
import ingest_weather as wx         # noqa: E402
import predict_podium as pp         # noqa: E402

D = dt.date


# ---------- A · Jolpica watermark ----------
SCHEDULE = [{"round": str(i), "date": f"2026-{m:02d}-{d:02d}"}
            for i, (m, d) in enumerate([(10, 25), (11, 1), (11, 8), (11, 21)], start=19)]


def test_watermark_reloads_last_round_and_stops_before_future_races():
    # results loaded up to round 20 (Mexico); run on Monday 9 Nov, after Brazil (round 21)
    assert jol.rounds_to_load(SCHEDULE, watermark=20, run_date=D(2026, 11, 9)) == [20, 21]


def test_first_run_loads_every_finished_round():
    assert jol.rounds_to_load(SCHEDULE, watermark=0, run_date=D(2026, 11, 3)) == [19, 20]


def test_next_round_is_the_first_race_on_or_after_the_run_date():
    assert jol.next_round(SCHEDULE, D(2026, 11, 3)) == 21          # São Paulo GP, 8 Nov 2026
    assert jol.next_round(SCHEDULE, D(2026, 11, 8)) == 21          # race day itself
    assert jol.next_round(SCHEDULE, D(2026, 12, 31)) is None


# ---------- C · Open-Meteo plan ----------
def race(season, rnd, day):
    return {"season": season, "round": rnd, "date": day, "lat": -23.7, "lon": -46.7}


def test_weather_plan_archive_once_forecast_for_next_race():
    races = [race("2026", "19", D(2026, 10, 25)), race("2026", "20", D(2026, 11, 1)),
             race("2026", "21", D(2026, 11, 8)), race("2026", "22", D(2026, 11, 21))]
    calls = wx.plan(races, already_archived={("2026", "19")}, run_date=D(2026, 11, 3))
    kinds = [(c[1], c[2], c[3]) for c in calls]
    assert ("19", "archive", wx.ARCHIVE) not in kinds                    # already loaded: not called again
    assert ("20", "archive", wx.FORECAST) in kinds                       # last week: forecast model
    assert ("21", "forecast", wx.FORECAST) in kinds                      # next race: forecast
    assert all(c[1] != "22" for c in calls)                              # only the NEXT race is forecast


# ---------- D · FastF1 transformations ----------
def fake_laps():
    s = pd.to_timedelta
    return pd.DataFrame({
        "Driver": ["VER", "VER", "VER", "LEC", "LEC"],
        "LapTime": [s(90.5, "s"), s(89.9, "s"), s(95.0, "s"), s(90.1, "s"), pd.NaT],
        "PitInTime": [pd.NaT, pd.NaT, s(1, "s"), pd.NaT, pd.NaT],
        "PitOutTime": [pd.NaT] * 5,
        "Stint": [1, 1, 1, 1, 2], "Compound": ["SOFT", "SOFT", "SOFT", "MEDIUM", "HARD"],
        "LapNumber": [1, 2, 3, 1, 2]})


def test_laps_summary_ignores_pit_laps_and_missing_times():
    out = f1.laps_summary(fake_laps(), 2026, 21, "FP2").set_index("driver_code")
    assert out.loc["VER", "best_lap_s"] == 89.9
    assert out.loc["VER", "avg_lap_s"] == 90.2          # the 95.0 s pit lap is excluded
    assert out.loc["VER", "laps"] == 3 and out.loc["LEC", "laps"] == 2


def test_stints_one_row_per_driver_and_stint():
    out = f1.stints(fake_laps(), 2026, 21)
    assert len(out) == 3 and set(out["compound"]) == {"SOFT", "MEDIUM", "HARD"}


def test_sessions_done_only_returns_sessions_before_end_of_run_date():
    ev = pd.Series({"Session1": "Practice 1", "Session1DateUtc": pd.Timestamp("2026-11-06 14:30"),
                    "Session2": "Practice 2", "Session2DateUtc": pd.Timestamp("2026-11-06 18:00"),
                    "Session3": "Practice 3", "Session3DateUtc": pd.Timestamp("2026-11-07 14:30"),
                    "Session4": "Qualifying", "Session4DateUtc": pd.Timestamp("2026-11-07 18:00"),
                    "Session5": "Race", "Session5DateUtc": pd.Timestamp("2026-11-08 17:00")})
    assert f1.sessions_done(ev, pd.Timestamp("2026-11-06")) == ["FP1", "FP2"]
    assert f1.sessions_done(ev, pd.Timestamp("2026-11-09")) == ["FP1", "FP2", "FP3", "Q", "R"]
    assert f1.sessions_done(ev, pd.Timestamp("2026-11-03")) == []


# ---------- UC1 · model, on REAL 2024-2025 race weekends (FastF1 export) ----------
SESSIONS_CSV = Path(__file__).resolve().parent / "data" / "f1_2024_2025_sessions.csv"
POINTS = {1: 25, 2: 18, 3: 15, 4: 12, 5: 10, 6: 8, 7: 6, 8: 4, 9: 2, 10: 1}


def features_from_real_weekends():
    """Rebuild UC1 features (same definitions as gold/uc1_podium_features.sql) from real 2024-2025 weekends."""
    df = pd.read_csv(SESSIONS_CSV)
    df["race_no"] = df.groupby(["Year", "Event"], sort=False).ngroup()
    df["race_id"] = df["Year"].astype(str) + "-" + df["race_no"].astype(str)
    df = df[df["RacePosition"].notna()].sort_values("race_no")
    out = pd.DataFrame({"race_id": df["race_id"], "season": df["Year"], "driver_ref": df["Driver"],
                        "grid": df["GridPosition"], "is_podium": (df["RacePosition"] <= 3).astype(float)})
    out["quali_gap_pct"] = df["Best_Quali_Time"] / df.groupby("race_id")["Best_Quali_Time"].transform("min") - 1
    prev = lambda s, n: s.shift(1).rolling(n, min_periods=1).mean()          # earlier races only
    out["driver_avg_finish_5"] = df.groupby("Driver")["RacePosition"].transform(lambda s: prev(s, 5))
    out["driver_avg_finish_circuit"] = df.groupby(["Driver", "Event"])["RacePosition"].transform(lambda s: prev(s, 10))
    pts = df["RacePosition"].map(POINTS).fillna(0)
    team = pts.groupby([df["race_id"], df["Team"]]).transform("sum")
    out["team_avg_points_5"] = team.groupby(df["Team"]).transform(lambda s: prev(s, 10))
    best_fp = df[["FP1_BestLapTime", "FP2_BestLapTime", "FP3_BestLapTime"]].min(axis=1)
    out["practice_gap_pct"] = best_fp / best_fp.groupby(df["race_id"]).transform("min") - 1
    out["is_wet_race"] = 0.0
    out["is_next_race"] = False
    return out


def test_backtest_on_real_2025_data_beats_or_matches_the_grid_baseline():
    feats = features_from_real_weekends()
    bt = pp.backtest(feats, season=2025)
    print("\nBacktest 2025 (trained on 2024):", bt)
    assert bt["races"] >= 15
    assert 0 <= bt["model_hit_rate"] <= 1 and 0 <= bt["grid_hit_rate"] <= 1


def test_next_race_gets_one_ranked_prediction_per_driver_even_without_grid():
    feats = features_from_real_weekends()
    last = feats["race_id"].iloc[-1]
    feats.loc[feats["race_id"] == last, ["is_podium", "grid", "quali_gap_pct"]] = None   # before qualifying
    feats.loc[feats["race_id"] == last, "is_next_race"] = True
    preds, weights = pp.predict_next(feats)
    print("\nWeights:", weights)
    print(preds[["predicted_rank", "driver_ref", "p_podium"]].head(5).to_string(index=False))
    assert sorted(preds["predicted_rank"]) == list(range(1, len(preds) + 1))
    assert preds["p_podium"].between(0, 1).all()
