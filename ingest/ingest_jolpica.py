"""Source A · Jolpica-F1 API -> BRONZE.JOLPICA_RAW (raw JSON, one row per call).

Mode: INCREMENTAL API PULL with a watermark (course: 04_incremental_watermark.md).
  1. reload the season calendar (it can change during the season)
  2. watermark = last round whose results are already in bronze
  3. load results, qualifying and pit stops from the watermark up to the last race before --run-date
     (the last loaded round is loaded AGAIN: post-race penalties change results; MERGE replaces the row)
  4. load the qualifying of the next race as soon as it exists (needed for the prediction)

  python ingest_jolpica.py --run-date 2026-11-09
Rate limit of the API: about 4 calls/second and 500/hour -> we pause between calls.
"""
import argparse
import datetime as dt
import time

from common import RUN_ID, connect, get_json, merge_json

BASE = "https://api.jolpi.ca/ergast/f1"
TABLE = "BRONZE.JOLPICA_RAW"


def races_of(payload):
    return payload["MRData"]["RaceTable"]["Races"]


def rounds_to_load(schedule, watermark, run_date):
    """Rounds whose race is over (date < run_date), starting again at the watermark."""
    done = [int(r["round"]) for r in schedule if dt.date.fromisoformat(r["date"]) < run_date]
    return [r for r in done if r >= max(watermark, 1)]


def next_round(schedule, run_date):
    upcoming = [r for r in schedule if dt.date.fromisoformat(r["date"]) >= run_date]
    return int(upcoming[0]["round"]) if upcoming else None


def load(cur, season, rnd, endpoint):
    payload = get_json(f"{BASE}/{season}/{rnd}/{endpoint}/", params={"limit": 100})
    merge_json(cur, TABLE, {"ENDPOINT": endpoint, "SEASON": str(season), "ROUND": str(rnd)}, payload, "jolpica")
    time.sleep(0.5)
    return len(races_of(payload))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--run-date", default=str(dt.date.today()), help="Airflow passes {{ ds }}")
    ap.add_argument("--season", type=int, help="default: the season of --run-date")
    a = ap.parse_args()
    run_date = dt.date.fromisoformat(a.run_date)
    season = a.season or run_date.year
    print(f"Jolpica ingestion · season {season} · run date {run_date} · run {RUN_ID}")

    con = connect()
    cur = con.cursor()
    try:
        schedule_payload = get_json(f"{BASE}/{season}/", params={"limit": 100})
        merge_json(cur, TABLE, {"ENDPOINT": "schedule", "SEASON": str(season), "ROUND": "0"},
                   schedule_payload, "jolpica")
        schedule = races_of(schedule_payload)
        print(f"  calendar: {len(schedule)} races")

        cur.execute(f"""SELECT COALESCE(MAX(TRY_TO_NUMBER(ROUND)), 0) FROM {TABLE}
                        WHERE ENDPOINT = 'results' AND SEASON = %s
                          AND ARRAY_SIZE(PAYLOAD:MRData:RaceTable:Races) > 0""", (str(season),))
        watermark = cur.fetchone()[0]
        todo = rounds_to_load(schedule, watermark, run_date)
        print(f"  watermark: round {watermark} -> rounds to (re)load: {todo}")

        for rnd in todo:
            found = load(cur, season, rnd, "results")
            if found == 0:          # race over but results not published yet: stop, the next run retries
                print(f"  round {rnd}: no results yet, stopping here")
                break
            load(cur, season, rnd, "qualifying")
            load(cur, season, rnd, "pitstops")
            print(f"  round {rnd}: results, qualifying, pit stops loaded")

        nxt = next_round(schedule, run_date)
        if nxt and load(cur, season, nxt, "qualifying"):
            print(f"  next race (round {nxt}): qualifying already available")
    finally:
        cur.close()
        con.close()


if __name__ == "__main__":
    main()
