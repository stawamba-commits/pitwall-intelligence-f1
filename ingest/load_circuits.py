"""Source E · f1-circuits (github.com/bacinger/f1-circuits) -> BRONZE.CIRCUITS_RAW.

Mode: STATIC FILE (GeoJSON) loaded once, then again only if the file changes (new circuit).
One raw JSON row per circuit (a GeoJSON "Feature": name, location, length, altitude, track outline).

  python load_circuits.py
"""
from common import RUN_ID, connect, get_json, merge_json

URL = "https://raw.githubusercontent.com/bacinger/f1-circuits/master/f1-circuits.geojson"


def main():
    print(f"f1-circuits load · run {RUN_ID}")
    features = get_json(URL)["features"]
    con = connect()
    cur = con.cursor()
    try:
        for f in features:
            p = f["properties"]
            key = str(p.get("id") or p.get("Name"))           # file's own id, else the circuit name
            merge_json(cur, "BRONZE.CIRCUITS_RAW", {"CIRCUIT_KEY": key}, f, "f1-circuits")
        print(f"  {len(features)} circuits loaded")
    finally:
        cur.close()
        con.close()


if __name__ == "__main__":
    main()
