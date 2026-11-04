"""PitWall Analytics · helpers shared by every ingestion job.

Same patterns as the course:
  - key-pair connection to Snowflake (the key is mounted at run time, never in the image)
  - API calls with a timeout, retries and raise_for_status (visible failures)
  - bronze keeps the data AS RECEIVED, plus _source, _loaded_at and _run_id
  - loads are idempotent: MERGE on a business key, so a replay never duplicates
"""
import json
import os
import time
import uuid
from pathlib import Path

import requests

DATABASE = os.environ.get("PITWALL_DATABASE", "PITWALL")
RUN_ID = os.environ.get("PITWALL_RUN_ID") or uuid.uuid4().hex[:12]   # Airflow passes its run id


def connect():
    import snowflake.connector
    from cryptography.hazmat.primitives import serialization

    key = serialization.load_pem_private_key(
        Path(os.environ["SNOWFLAKE_PRIVATE_KEY_FILE"]).read_bytes(), password=None)
    return snowflake.connector.connect(
        account=os.environ["SNOWFLAKE_ACCOUNT"], user=os.environ["SNOWFLAKE_USER"],
        private_key=key.private_bytes(serialization.Encoding.DER, serialization.PrivateFormat.PKCS8,
                                      serialization.NoEncryption()),
        role=os.environ.get("SNOWFLAKE_ROLE", "PITWALL_PIPELINE"),
        warehouse=os.environ.get("SNOWFLAKE_WAREHOUSE", "PITWALL_ELT_WH"),
        database=DATABASE, schema="BRONZE")


def get_json(url, params=None, retries=4, pause=2.0):
    """GET with timeout and retry. HTTP 429 (rate limit) and 5xx are retried, then we FAIL LOUDLY."""
    if os.environ.get("PITWALL_SIMULATE_OUTAGE") == "1":          # incident drill A (docs/incidents.md)
        raise ConnectionError(f"Simulated outage: {url} is unreachable")
    for attempt in range(1, retries + 1):
        r = requests.get(url, params=params, timeout=30)
        if r.status_code == 429 or r.status_code >= 500:
            print(f"  {url} answered {r.status_code}, retry {attempt}/{retries} in {pause * attempt:.0f}s")
            time.sleep(pause * attempt)
            continue
        r.raise_for_status()
        return r.json()
    r.raise_for_status()
    raise RuntimeError(f"{url} still failing after {retries} retries")


def merge_json(cur, table, keys, payload, source):
    """Upsert ONE raw JSON document into a bronze VARIANT table.

    keys = business key, e.g. {"SEASON": "2026", "ROUND": "21", "ENDPOINT": "results"}.
    Re-running the same call replaces the row instead of adding a second one (idempotent).
    """
    cols = list(keys)
    cur.execute(f"""CREATE TABLE IF NOT EXISTS {table} (
        {", ".join(f"{c} VARCHAR" for c in cols)},
        PAYLOAD VARIANT, _SOURCE VARCHAR, _LOADED_AT TIMESTAMP_TZ, _RUN_ID VARCHAR)""")
    on = " AND ".join(f"t.{c} = s.{c}" for c in cols)
    cur.execute(f"""
        MERGE INTO {table} t
        USING (SELECT {", ".join(f"%s AS {c}" for c in cols)}, PARSE_JSON(%s) AS PAYLOAD) s
        ON {on}
        WHEN MATCHED THEN UPDATE SET t.PAYLOAD = s.PAYLOAD, t._SOURCE = %s,
             t._LOADED_AT = CURRENT_TIMESTAMP(), t._RUN_ID = %s
        WHEN NOT MATCHED THEN INSERT ({", ".join(cols)}, PAYLOAD, _SOURCE, _LOADED_AT, _RUN_ID)
             VALUES ({", ".join(f"s.{c}" for c in cols)}, s.PAYLOAD, %s, CURRENT_TIMESTAMP(), %s)""",
                (*keys.values(), json.dumps(payload), source, RUN_ID, source, RUN_ID))


def merge_dataframe(con, df, table, keys, source):
    """Bulk-load a DataFrame (all columns as text) into bronze with write_pandas + MERGE.

    write_pandas uploads the rows as Parquet to a Snowflake stage and runs COPY INTO a staging table;
    the MERGE on the business key then makes the load replayable (course: 03_python_write_pandas.py).
    """
    from snowflake.connector.pandas_tools import write_pandas

    if df.empty:
        print(f"  {table}: nothing to load")
        return
    df = df.astype(str).replace({"nan": None, "NaT": None, "None": None, "<NA>": None})
    df.columns = [c.upper() for c in df.columns]
    df["_SOURCE"], df["_RUN_ID"] = source, RUN_ID
    keys = [k.upper() for k in keys]
    df = df.drop_duplicates(subset=keys, keep="last")
    cur = con.cursor()
    cur.execute(f"CREATE TABLE IF NOT EXISTS {table} ({', '.join(f'{c} VARCHAR' for c in df.columns)}, "
                f"_LOADED_AT TIMESTAMP_TZ)")
    # schema drift: a new column in the source is added as text instead of breaking the load
    cur.execute(f"SHOW COLUMNS IN TABLE {table}")
    existing = {row[2] for row in cur.fetchall()}
    for c in df.columns:
        if c not in existing:
            print(f"  schema drift: new column {c} added to {table}")
            cur.execute(f"ALTER TABLE {table} ADD COLUMN {c} VARCHAR")
    schema, name = table.split(".")
    write_pandas(con, df, f"{name}_STAGING", schema=schema, auto_create_table=True, overwrite=True,
                 quote_identifiers=False)
    on = " AND ".join(f"t.{k} = s.{k}" for k in keys)
    cols = list(df.columns)
    cur.execute(f"""
        MERGE INTO {table} t USING {table}_STAGING s ON {on}
        WHEN MATCHED THEN UPDATE SET {", ".join(f"t.{c} = s.{c}" for c in cols)}, t._LOADED_AT = CURRENT_TIMESTAMP()
        WHEN NOT MATCHED THEN INSERT ({", ".join(cols)}, _LOADED_AT)
             VALUES ({", ".join(f"s.{c}" for c in cols)}, CURRENT_TIMESTAMP())""")
    inserted, updated = cur.fetchone()
    print(f"  {table}: {inserted} inserted, {updated} updated (run {RUN_ID})")
