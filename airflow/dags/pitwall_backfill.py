"""PitWall Analytics · one-off loads, triggered by hand (schedule=None).

    load_circuits  (E · GeoJSON file)
    load_kaggle    (B · history 1950-2024, CSV files put in PITWALL_KAGGLE_DIR beforehand)
    jolpica_2025   (A · the 2025 season, not in the Kaggle file)
    fastf1_history (D · timing data since 2023, slow: cached)
All of them are idempotent (MERGE): running this DAG twice does not duplicate anything.
"""
import os

import pendulum
from airflow.sdk import DAG
from docker.types import Mount

from pitwall_common import CACHE_MOUNT, alert_on_failure, job

KAGGLE_MOUNT = [Mount(source=os.environ.get("PITWALL_KAGGLE_DIR", "/tmp/kaggle"), target="/data/kaggle",
                      type="bind", read_only=True)]

with DAG(
    dag_id="pitwall_backfill",
    schedule=None,
    start_date=pendulum.datetime(2026, 11, 1, tz="Europe/Paris"),
    catchup=False,
    default_args={"retries": 1, "on_failure_callback": alert_on_failure},
    tags=["pitwall"],
) as dag:
    load_circuits = job("load_circuits", "python load_circuits.py")
    load_kaggle = job("load_kaggle", "python load_kaggle.py --path /data/kaggle", mounts=KAGGLE_MOUNT)
    jolpica_2025 = job("jolpica_2025", "python ingest_jolpica.py --season 2025 --run-date 2026-01-01")
    fastf1_history = job("fastf1_history", "python ingest_fastf1.py --backfill-from 2023 --run-date {{ ds }}",
                         mounts=CACHE_MOUNT)
    weather_history = job("weather_history", "python ingest_weather.py --from-season 2018 --run-date {{ ds }}")

    [load_kaggle, jolpica_2025] >> weather_history
