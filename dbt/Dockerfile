# PitWall Analytics · image that runs the dbt project (bronze -> silver -> gold + tests)
# Build:  docker build -t pitwall-dbt:1.0.0 dbt/
FROM python:3.12.7-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1 \
    DBT_PROFILES_DIR=/app

WORKDIR /app

COPY requirements.txt .
RUN pip install -r requirements.txt

COPY pitwall_dbt/ .

RUN useradd --create-home --uid 1000 pitwall && chown -R pitwall /app
USER pitwall

CMD ["dbt", "build"]
