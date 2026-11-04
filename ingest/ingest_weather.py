"""Source C · Open-Meteo -> BRONZE.WEATHER_RAW (raw JSON, one row per race and kind).

Mode: API PULL (course: 05_api_to_snowflake.py). The circuits' coordinates come from the calendar already
loaded by ingest_jolpica.py, so this job runs AFTER it.
  - past races  : hourly weather of the race weekend (archive API, loaded once)
  - next race   : hourly FORECAST (refreshed at every run until the race)

  python ingest_weather.py --run-date 2026-11-05
"""
import argparse
import datetime as dt

from common import RUN_ID, connect, get_json, merge_json

ARCHIVE = "https://archive-api.open-meteo.com/v1/archive"
FORECAST = "https://api.open-meteo.com/v1/forecast"
HOURLY = "temperature_2m,precipitation,rain,wind_speed_10m,relative_humidity_2m"
TABLE = "BRONZE.WEATHER_RAW"


def plan(races, already_archived, run_date):
    """Decide what to call for each race: (season, round, kind, url, params)."""
    calls, upcoming = [], [r for r in races if r["date"] >= run_date]
    for r in races:
        start, end = str(r["date"] - dt.timedelta(days=2)), str(r["date"])   # Friday -> Sunday
        base = {"latitude": r["lat"], "longitude": r["lon"], "hourly": HOURLY, "timezone": "UTC",
                "start_date": start, "end_date": end}
        if r["date"] < run_date - dt.timedelta(days=7):
            if (r["season"], r["round"]) not in already_archived:
                calls.append((r["season"], r["round"], "archive", ARCHIVE, base))
        elif r["date"] < run_date:      # last week: the archive is not complete yet, use the forecast model
            calls.append((r["season"], r["round"], "archive", FORECAST, base))
        elif upcoming and r is upcoming[0] and r["date"] <= run_date + dt.timedelta(days=15):
            calls.append((r["season"], r["round"], "forecast", FORECAST,
                          {**base, "hourly": HOURLY + ",precipitation_probability"}))
    return calls


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--run-date", default=str(dt.date.today()))
    ap.add_argument("--from-season", type=int, default=2018)
    a = ap.parse_args()
    run_date = dt.date.fromisoformat(a.run_date)
    print(f"Open-Meteo ingestion · run date {run_date} · run {RUN_ID}")

    con = connect()
    cur = con.cursor()
    try:
        # Calendar of the Jolpica seasons + (if already loaded) the Kaggle history, Jolpica first
        cur.execute("SHOW TABLES LIKE 'KAGGLE_RACES' IN SCHEMA BRONZE")
        kaggle = """UNION ALL SELECT r.YEAR, r.ROUND, TRY_TO_DATE(r.DATE), TRY_TO_DOUBLE(c.LAT),
                           TRY_TO_DOUBLE(c.LNG), 2
                    FROM BRONZE.KAGGLE_RACES r JOIN BRONZE.KAGGLE_CIRCUITS c ON c.CIRCUITID = r.CIRCUITID
                 """ if cur.fetchall() else ""
        cur.execute(f"""SELECT season, round, race_date, lat, lon FROM (
                          SELECT r.value:season::STRING season, r.value:round::STRING round,
                                 r.value:date::DATE race_date, r.value:Circuit:Location:lat::FLOAT lat,
                                 r.value:Circuit:Location:long::FLOAT lon, 1 priority
                          FROM BRONZE.JOLPICA_RAW j, LATERAL FLATTEN(j.PAYLOAD:MRData:RaceTable:Races) r
                          WHERE j.ENDPOINT = 'schedule'
                          {kaggle})
                        WHERE TRY_TO_NUMBER(season) >= %s
                        QUALIFY ROW_NUMBER() OVER (PARTITION BY season, round ORDER BY priority) = 1
                        ORDER BY race_date""", (a.from_season,))
        races = [dict(zip(["season", "round", "date", "lat", "lon"], row)) for row in cur.fetchall()]
        cur.execute(f"CREATE TABLE IF NOT EXISTS {TABLE} (SEASON VARCHAR, ROUND VARCHAR, KIND VARCHAR, "
                    "PAYLOAD VARIANT, _SOURCE VARCHAR, _LOADED_AT TIMESTAMP_TZ, _RUN_ID VARCHAR)")
        cur.execute(f"SELECT SEASON, ROUND FROM {TABLE} WHERE KIND = 'archive'")
        already = {(s, r) for s, r in cur.fetchall()}

        calls = plan(races, already, run_date)
        print(f"  {len(races)} races in the calendar, {len(calls)} weather calls to make")
        for season, rnd, kind, url, params in calls:
            payload = get_json(url, params=params)
            merge_json(cur, TABLE, {"SEASON": season, "ROUND": rnd, "KIND": kind}, payload, "open-meteo")
            print(f"  {season} round {rnd}: {kind} ({len(payload['hourly']['time'])} hours)")
    finally:
        cur.close()
        con.close()


if __name__ == "__main__":
    main()
