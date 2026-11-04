# PitWall Analytics · image that runs the ingestion jobs and the UC1 model
# Build:  docker build -t pitwall-jobs:1.0.0 ingest/
FROM python:3.12.7-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1 \
    FASTF1_CACHE=/cache

WORKDIR /app

# 1. Dependencies first: this layer stays in the cache while requirements.txt does not change
COPY requirements.txt .
RUN pip install -r requirements.txt

# 2. Then only the jobs: no data, no key, no .env (see .dockerignore)
COPY common.py ingest_jolpica.py ingest_weather.py ingest_fastf1.py load_kaggle.py load_circuits.py predict_podium.py ./

# 3. Not root. /cache is a volume so the FastF1 cache survives between runs (rate limit)
RUN useradd --create-home --uid 1000 pitwall && mkdir /cache && chown pitwall /cache
USER pitwall

CMD ["python", "ingest_jolpica.py"]
