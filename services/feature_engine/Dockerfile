FROM python:3.11-slim

WORKDIR /app

RUN pip install --no-cache-dir uv

COPY libs/ /app/libs/
COPY services/feature_engine/ /app/services/feature_engine/

WORKDIR /app/libs

RUN uv pip install --system -e .

WORKDIR /app/services/feature_engine

RUN uv pip install --system -e .

WORKDIR /app

ENV PYTHONPATH=/app

EXPOSE 8000

CMD ["python", "-m", "services.feature_engine.src.main"]
