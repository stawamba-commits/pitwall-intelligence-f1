"""Source D · FastF1 (official F1 live-timing data) -> 5 BRONZE.FASTF1_* tables.

Mode: PYTHON LIBRARY -> DataFrame -> write_pandas + MERGE (course: 03_python_write_pandas.py).
Timing data exists from 2018. We use the high-level API (get_session / load), not fastf1.api,
which the FastF1 docs say may become private.

  python ingest_fastf1.py --run-date 2026-11-09               # last finished weekend + next race practice
  python ingest_fastf1.py --run-date 2026-11-09 --backfill-from 2023

What we keep (no fine telemetry: the use cases do not need it):
  FASTF1_LAPS_SUMMARY  pace per driver and session   (UC1 podium, UC3 pit strategy)
  FASTF1_STINTS        tyre stints of the race       (UC3 pit strategy)
  FASTF1_TRACK_STATUS  flags, safety car, red flag   (UC5 safety-car risk)
  FASTF1_WEATHER       weather measured at the track (UC4 rain alert)
  FASTF1_RESULTS       session classification, AS RECEIVED (for non-winners "Time" is a GAP, fixed in silver)
"""
import argparse
import datetime as dt
import os

import pandas as pd

from common import RUN_ID, connect, merge_dataframe

SESSIONS = {"Practice 1": "FP1", "Practice 2": "FP2", "Practice 3": "FP3", "Qualifying": "Q", "Race": "R"}


def sessions_done(event, run_date):
    """Sessions of this weekend that were over before the end of the run date (sprints are ignored)."""
    until = run_date + pd.Timedelta(days=1)
    done = []
    for i in range(1, 6):
        name, start = event.get(f"Session{i}"), event.get(f"Session{i}DateUtc")
        if name in SESSIONS and pd.notna(start) and pd.Timestamp(start).tz_localize(None) < until:
            done.append(SESSIONS[name])
    return done


def seconds(td):
    return None if pd.isna(td) else round(td.total_seconds(), 3)


def laps_summary(laps, season, rnd, session):
    """One row per driver: best lap, average of clean laps, number of laps."""
    clean = laps[laps["LapTime"].notna() & laps["PitInTime"].isna() & laps["PitOutTime"].isna()]
    g = clean.groupby("Driver")["LapTime"]
    out = pd.DataFrame({"best_lap_s": g.min().map(seconds), "avg_lap_s": g.mean().map(seconds),
                        "laps": laps.groupby("Driver").size()}).reset_index()
    return out.rename(columns={"Driver": "driver_code"}).assign(season=season, round=rnd, session=session)


def stints(laps, season, rnd):
    s = (laps.groupby(["Driver", "Stint"])
             .agg(compound=("Compound", "first"), laps=("LapNumber", "count"),
                  first_lap=("LapNumber", "min"), last_lap=("LapNumber", "max"))
             .reset_index().rename(columns={"Driver": "driver_code", "Stint": "stint"}))
    return s.assign(season=season, round=rnd)


def timed_rows(df, season, rnd, session):
    """Track status / weather rows: keep every column, 'Time' (since session start) becomes seconds."""
    out = df.copy()
    out["Time"] = out["Time"].map(seconds)
    out.columns = [c.lower() for c in out.columns]
    return out.assign(season=season, round=rnd, session=session)


def results(res, season, rnd, session):
    cols = ["DriverNumber", "Abbreviation", "TeamName", "Position", "GridPosition", "Status", "Time"]
    out = res[cols].copy()
    out["Time"] = out["Time"].map(seconds)
    out.columns = ["driver_number", "driver_code", "team", "position", "grid", "status", "time_s"]
    return out.assign(season=season, round=rnd, session=session)


def collect(season, rnd, sessions):
    import fastf1
    frames = {k: [] for k in ["laps", "stints", "status", "weather", "results"]}
    for name in sessions:
        try:
            s = fastf1.get_session(season, rnd, name)
            s.load(laps=True, telemetry=False, weather=True, messages=True)
        except ValueError as e:          # e.g. no FP2/FP3 on a sprint weekend
            print(f"  {season} R{rnd} {name}: not available ({e})")
            continue
        frames["laps"].append(laps_summary(s.laps, season, rnd, name))
        frames["weather"].append(timed_rows(s.weather_data, season, rnd, name))
        if name in ("Q", "R"):
            frames["results"].append(results(s.results, season, rnd, name))
        if name == "R":
            frames["stints"].append(stints(s.laps, season, rnd))
            frames["status"].append(timed_rows(s.track_status, season, rnd, name))
        print(f"  {season} R{rnd} {name}: {len(s.laps)} laps")
    return {k: pd.concat(v) if v else pd.DataFrame() for k, v in frames.items()}


def main():
    import fastf1
    ap = argparse.ArgumentParser()
    ap.add_argument("--run-date", default=str(dt.date.today()))
    ap.add_argument("--backfill-from", type=int, help="first season to (re)load, e.g. 2023")
    a = ap.parse_args()
    run_date = pd.Timestamp(a.run_date)          # naive, compared with UTC session times
    cache = os.environ.get("FASTF1_CACHE", "/tmp/fastf1_cache")   # a Docker volume in production
    os.makedirs(cache, exist_ok=True)
    fastf1.Cache.enable_cache(cache)                              # cached calls do not count in the rate limit
    print(f"FastF1 ingestion · run date {run_date.date()} · run {RUN_ID}")

    con = connect()
    try:
        cur = con.cursor()
        cur.execute("CREATE TABLE IF NOT EXISTS BRONZE.FASTF1_RESULTS (SEASON VARCHAR, ROUND VARCHAR, "
                    "SESSION VARCHAR, DRIVER_CODE VARCHAR, _LOADED_AT TIMESTAMP_TZ)")
        cur.execute("SELECT DISTINCT SEASON, ROUND FROM BRONZE.FASTF1_RESULTS WHERE SESSION = 'R'")
        loaded = {(int(s), int(r)) for s, r in cur.fetchall()}

        todo = []
        for season in range(a.backfill_from or run_date.year, run_date.year + 1):
            cal = fastf1.get_event_schedule(season, include_testing=False)
            for _, ev in cal.iterrows():
                done = sessions_done(ev, run_date)
                if not done:
                    break                                      # the rest of the season is in the future
                rnd = int(ev["RoundNumber"])
                if "R" in done and (season, rnd) in loaded:
                    continue                                   # finished weekend already in bronze
                todo.append((season, rnd, done))               # finished weekend, or practice of the next one
        print(f"  weekends to load: {[(s, r, d) for s, r, d in todo]}")

        for season, rnd, sessions in todo:
            f = collect(season, rnd, sessions)
            merge_dataframe(con, f["laps"], "BRONZE.FASTF1_LAPS_SUMMARY",
                            ["season", "round", "session", "driver_code"], "fastf1")
            merge_dataframe(con, f["stints"], "BRONZE.FASTF1_STINTS",
                            ["season", "round", "driver_code", "stint"], "fastf1")
            merge_dataframe(con, f["status"], "BRONZE.FASTF1_TRACK_STATUS",
                            ["season", "round", "session", "time"], "fastf1")
            merge_dataframe(con, f["weather"], "BRONZE.FASTF1_WEATHER",
                            ["season", "round", "session", "time"], "fastf1")
            merge_dataframe(con, f["results"], "BRONZE.FASTF1_RESULTS",
                            ["season", "round", "session", "driver_code"], "fastf1")
    finally:
        con.close()


if __name__ == "__main__":
    main()
