# Stage 1 (builder)
FROM python:3.11-slim as builder

RUN apt-get update && apt-get install -y --no-install-recommends build-essential

WORKDIR /build
COPY pyproject.toml .
COPY README.md .
COPY src ./src
RUN python -m venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"
# Assuming pip install . is handled correctly
RUN pip install --upgrade pip && pip install .

# Stage 2 (runtime)
FROM python:3.11-slim

RUN apt-get update && apt-get install -y --no-install-recommends libmagic1 && rm -rf /var/lib/apt/lists/*

ENV PYTHONUNBUFFERED=1
ENV TIKA_CLIENT_ONLY=True
ENV ENTRYPOINT_SCRIPT="scripts/run_api.py"
ENV PATH="/opt/venv/bin:$PATH"

COPY --from=builder /opt/venv /opt/venv

WORKDIR /app
COPY src/ingestion /app/src/ingestion
COPY scripts /app/scripts
COPY alembic /app/alembic
COPY alembic.ini /app/alembic.ini
ENV PYTHONPATH="/app/src"

CMD python ${ENTRYPOINT_SCRIPT}
