FROM python:3.11-slim
ENV PYTHONUNBUFFERED=1 PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=/app:/app/services/ingestion/src
WORKDIR /app
RUN apt-get update && apt-get install -y --no-install-recommends libmagic1 ffmpeg libgomp1 curl git && rm -rf /var/lib/apt/lists/*
COPY pyproject.toml README.md ./
COPY modules ./modules
COPY services ./services
RUN pip install --no-cache-dir -e . -e ./services/ingestion -r services/download/requirements.txt -r services/search/backend/requirements.txt 'fastapi>=0.118,<1' 'kafka-python-ng==2.2.3' 'pytest-asyncio>=0.24' 'ruff>=0.6' 'mypy>=1.10' 'qdrant-client==1.11.1'
COPY scripts ./scripts
COPY server.py ./
COPY tests ./tests
COPY frontend/dist ./frontend/dist
CMD ["uvicorn", "server:app", "--host", "0.0.0.0", "--port", "8000"]
