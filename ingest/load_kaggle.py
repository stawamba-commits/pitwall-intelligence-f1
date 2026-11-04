"""Source B · Kaggle "Formula 1 World Championship (1950 - 2024)" CSV files -> BRONZE.KAGGLE_*.

Mode: ONE-OFF BATCH FILE LOAD (history since 1950). Manual step: download the dataset from kaggle.com
(free account), unzip it in data/kaggle/, then:

  python load_kaggle.py --path data/kaggle

Everything is loaded as TEXT, exactly as in the files (Kaggle writes missing values as \\N: silver cleans it).
MERGE on each file's key: running it twice changes nothing.
"""
import argparse
from pathlib import Path

import pandas as pd

from common import RUN_ID, connect, merge_dataframe

FILES = {                      # file -> business key
    "races.csv": ["raceId"],
    "results.csv": ["resultId"],
    "qualifying.csv": ["qualifyId"],
    "pit_stops.csv": ["raceId", "driverId", "stop"],
    "drivers.csv": ["driverId"],
    "constructors.csv": ["constructorId"],
    "circuits.csv": ["circuitId"],
    "status.csv": ["statusId"],
}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--path", default="data/kaggle")
    a = ap.parse_args()
    print(f"Kaggle batch load from {a.path} · run {RUN_ID}")
    con = connect()
    try:
        for name, key in FILES.items():
            df = pd.read_csv(Path(a.path) / name, dtype=str, keep_default_na=False)
            print(f"  {name}: {len(df)} rows")
            merge_dataframe(con, df, f"BRONZE.KAGGLE_{name[:-4].upper()}", key, f"kaggle/{name}")
    finally:
        con.close()


if __name__ == "__main__":
    main()
