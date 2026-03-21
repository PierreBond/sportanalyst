FROM python:3.11-slim

WORKDIR /app

RUN pip install --no-cache-dir uv

COPY libs/ /app/libs/
COPY services/model_training/ /app/services/model_training/

WORKDIR /app/libs

RUN uv pip install --system -e .

WORKDIR /app/services/model_training

RUN uv pip install --system -e .

WORKDIR /app

ENV PYTHONPATH=/app

CMD ["python", "-m", "services.model_training.src.train"]
