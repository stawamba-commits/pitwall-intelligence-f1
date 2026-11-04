# Incident scenarios (C6)

## A · The Jolpica API is down (or rate-limits us) on Monday morning — the drill we run live
**Symptom:** `ingest_jolpica` fails. **Detection:** the task fails visibly (`raise_for_status`, retries on 429/5xx),
Airflow retries twice (5 min apart), then `alert_on_failure` posts to Slack.
**Effect:** `dbt_build` and `predict_podium` do not run → the dashboard keeps yesterday's correct data
(it shows its freshness date). **Recovery:** nothing to clean. The next run starts again from the watermark
(last round loaded) and catches up all missed rounds. If 2 days pass, `assert_completed_races_have_results` fails:
the gap cannot go unnoticed.

How to show it live: in Airflow, *Trigger DAG w/ config* `{"simulate_outage": "1"}` on `pitwall_daily`
(or run `docker run -e PITWALL_SIMULATE_OUTAGE=1 ... python ingest_jolpica.py`) → red task, retries, alert.

## B · The same day is loaded twice (Airflow retry, manual re-run) — drill with before/after counts
**Risk:** double counting (the course's Airflow lab bug: revenue doubled while every task was green).
**Why it cannot happen here:** every bronze load is a `MERGE` on the business key
(`ENDPOINT+SEASON+ROUND`, `SEASON+ROUND+KIND`, `SEASON+ROUND+SESSION+DRIVER`...), silver de-duplicates with a
deterministic `qualify row_number()`, the model DELETEs then INSERTs the predictions of a race.
**Proof:** `sql/03_incident_drills.sql` drill B — counts before / after a second run are identical,
and the key tests (`unique_combination`) pass.

## C · A source sends an impossible result (two winners) — injected anomaly
`sql/03_incident_drills.sql` drill C appends a fake winner to a finished race, as a broken loader would.
`dbt build` → `assert_one_winner_per_race` **fails**, every model downstream of `fact_race_result` is **skipped**,
so the wrong number never reaches the dashboard. Recovery: delete the bad rows (`_SOURCE = 'incident-drill'`), rebuild.

## Known data bug, fixed: FastF1 race time is a gap
Found while profiling FastF1 (2024-2025 seasons): for 530 of 575 classified drivers, the race "Time" is the gap to
the winner, not the total time. Silver repairs it (`stg_fastf1_results.sql`), and the business-rule test
`assert_race_time_not_below_winner.sql` would fail if it came back.
