# Decisions (the questions the panel asks)

## Company and assumptions (C1)
- **PitWall Analytics** (fictional), 2 data engineers. Customers: fantasy F1 players (B2C subscription,
  assumed €4.99/month) and sports media (B2B licence for previews). 24 races per season.
- Constraint: predictions published **within 2 hours after qualifying**; refresh after every session.
- Constraint: cloud budget **≤ 10 Snowflake credits per month** (resource monitor, `sql/02_budget_monitor.sql`).

## Use cases: metric, grain, exclusions, frequency, acceptance (C2)
| UC | Metric (formula) | Grain | Excluded | Frequency | Accepted if |
|---|---|---|---|---|---|
| 1 | P(podium) from a logistic regression | race × driver | non-starters, cancelled races | after each session (daily run) | on last season, model finds more podium finishers than "top 3 of the grid" |
| 2 | places gained = grid − finish | race × driver | retired drivers, pit-lane starts (grid 0) | Monday after the race | equals a hand-run SQL check on 3 races |
| 3 | average and usual number of stops, compounds used | circuit (last 3 seasons) | retired drivers | before the race week | stops match the race reports of 3 races |
| 4 | max rain probability per session window, alert LOW/MEDIUM/HIGH (30 % / 60 %) | next race × session | — | daily during the race week | forecast compared with rain measured by FastF1 after the race |
| 5 | share of races with a safety car or VSC | circuit (last 5 seasons) | seasons before 2018 (no timing data) | before the race week | equals the count of SC flags in FastF1 |

**UC1 result on known data** (`pytest tests -s`, real 2024 → 2025 race weekends):
the model found **79.4 %** of the real podium finishers of 2025, the grid baseline **76.2 %** → accepted.
In production (Snowflake) the same backtest runs at every run on **2025 and on the 2026 races already
finished** before São Paulo, trained on all earlier races: results in `GOLD.UC1_MODEL_BACKTEST`.
The unit test uses a frozen 2024-2025 extract (`tests/data/`) so that it runs anywhere without network or Snowflake.

## Ingestion modes: requirement → mode → why not the others (C3, C4)
| Source | Mode | Why |
|---|---|---|
| A Jolpica-F1 | incremental API pull, watermark = last round loaded | new results once per race; the last round is reloaded to catch post-race penalties |
| B Kaggle | one-off batch file load | history 1950-2024 never changes |
| C Open-Meteo | API pull | archive once per past race, forecast refreshed daily for the next race |
| D FastF1 | Python library → DataFrame → write_pandas | official timing data, only a library gives it; cache = fewer calls (rate limit) |
| E f1-circuits | static file | changes only when a new circuit appears |
**No streaming (Kafka):** the decisions are taken once per session; "the board looks at it every morning" is a batch requirement.

## Tools and credible alternatives (C4)
| Need | Choice | Alternative and why not |
|---|---|---|
| warehouse | Snowflake | BigQuery would also work; Snowflake is the course platform, VARIANT handles raw JSON, per-second billing |
| transformations + tests | dbt | SQL scripts in Snowflake Tasks: no tests, no lineage graph |
| orchestration | Airflow + DockerOperator | GitHub Actions cron: no retries per task, no graph; Snowflake Tasks: cannot run FastF1 (Python library) |
| containers | Docker | a script on a laptop: not reproducible |
| IaC | Terraform | clicks in Snowsight: no review, no drift detection |
| model | scikit-learn logistic regression | gradient boosting: harder to explain, and ~24 races a year is a small dataset; logistic shows one weight per feature |
| dashboard | Streamlit in Snowflake | Power BI: Windows only, one more tool to install |

## Data decisions
1. **Which version wins** when a result exists twice? Jolpica (live source, corrected after penalties) before
   Kaggle, then the latest `_loaded_at`, then `constructor_ref` as tie-breaker → deterministic.
2. **Grain and key** of each gold table: written at the top of each model and tested (`unique_combination`).
   Never grouped by a name: by `driver_ref`, `constructor_ref`, `circuit_ref`.
3. **Repair, NULL or quarantine?** Repair when the rule is certain (FastF1 race time = winner time + gap; `\N` → NULL);
   quarantine when the row would make a number wrong (unknown race, impossible position) → `results_quarantine`.
4. **Time zone:** all timestamps in UTC; the run date (Airflow `{{ ds }}`) is in Europe/Paris, the company's time zone.
5. **Most recent data counts most:** the model is trained on every finished race, but each season back
   weighs half as much (the cars change every year, and completely in 2026). The next race is scored with the
   latest information only: form over the last 5 races, the qualifying grid, practice pace, the rain forecast.
6. **No leakage in the model:** form features only use races BEFORE the one predicted (`rows ... 1 preceding`).
