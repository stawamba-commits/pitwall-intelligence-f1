"""PitWall Analytics · daily pipeline (same structure as the course's redgrave_daily DAG).

    ingest_jolpica ──> ingest_weather ──┐
    ingest_fastf1 ──────────────────────┴──> dbt_build ──> predict_podium

Every task is a Docker container: Airflow only decides WHEN and IN WHAT ORDER they run,
retries them and alerts on failure. Why daily and not real time? The decisions are taken once per
session (after practice, after qualifying, the Monday after the race): batch is enough.
"""
import pendulum
from airflow.sdk import DAG

from pitwall_common import CACHE_MOUNT, alert_on_failure, job

with DAG(
    dag_id="pitwall_daily",
    schedule="0 7 * * *",                        # 07:00 Paris time, summer and winter
    start_date=pendulum.datetime(2026, 11, 1, tz="Europe/Paris"),
    catchup=False,
    max_active_runs=1,                           # one day at a time: no two dbt runs in parallel
    # Incident drill A: "Trigger DAG w/ config" {"simulate_outage": "1"} -> the Jolpica task fails on purpose
    params={"simulate_outage": "0"},
    default_args={"retries": 2, "retry_delay": pendulum.duration(minutes=5),
                  "on_failure_callback": alert_on_failure},
    tags=["pitwall"],
) as dag:
    # The date comes from the run ({{ ds }}), never from "today": backfills and replays work.
    ingest_jolpica = job("ingest_jolpica", "python ingest_jolpica.py --run-date {{ ds }}",
                         PITWALL_SIMULATE_OUTAGE="{{ params.simulate_outage }}")
    ingest_weather = job("ingest_weather", "python ingest_weather.py --run-date {{ ds }}")
    ingest_fastf1 = job("ingest_fastf1", "python ingest_fastf1.py --run-date {{ ds }}", mounts=CACHE_MOUNT)
    dbt_build = job("dbt_build",
                    "bash -c \"dbt source freshness && dbt build --vars '{run_date: {{ ds }}}'\"",
                    image="pitwall-dbt:1.0.0")
    predict = job("predict_podium", "python predict_podium.py --run-date {{ ds }}")

    ingest_jolpica >> ingest_weather          # the weather job needs the calendar (circuit coordinates)
    [ingest_weather, ingest_fastf1] >> dbt_build >> predict
