-- f1-circuits GeoJSON (E): one row per circuit, with the centre of the track outline.
-- The file has its own ids, so we match it to the Jolpica circuits by position (closest centre, < ~5 km).
with geo as (
    select
        c.circuit_key,
        c.payload:properties:Name::string       as name,
        c.payload:properties:Location::string   as location,
        try_to_number(c.payload:properties:length::string)   as length_m,
        try_to_number(c.payload:properties:altitude::string) as altitude_m,
        avg(p.value[1]::float) as centre_lat,          -- GeoJSON points are [longitude, latitude]
        avg(p.value[0]::float) as centre_lon
    from {{ source('bronze', 'circuits_raw') }} c,
         lateral flatten(input => c.payload:geometry:coordinates) p
    group by 1, 2, 3, 4, 5
),
jolpica_circuits as (
    select distinct circuit_ref, circuit_name, country, lat, lon from {{ ref('stg_races') }}
    where circuit_ref is not null
)
select
    j.circuit_ref, j.circuit_name, j.country, j.lat, j.lon,
    g.circuit_key as geojson_key, g.length_m, g.altitude_m
from jolpica_circuits j
left join geo g
  on abs(g.centre_lat - j.lat) < 0.05 and abs(g.centre_lon - j.lon) < 0.05
qualify row_number() over (partition by j.circuit_ref
                           order by abs(g.centre_lat - j.lat) + abs(g.centre_lon - j.lon) nulls last) = 1
