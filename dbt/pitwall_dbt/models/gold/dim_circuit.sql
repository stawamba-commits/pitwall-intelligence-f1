-- One row per circuit: Jolpica/Kaggle reference + length and altitude from the f1-circuits file.
select circuit_ref, circuit_name, country, lat, lon, length_m, altitude_m, geojson_key
from {{ ref('stg_circuits') }}
