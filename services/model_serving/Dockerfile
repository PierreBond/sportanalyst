FROM python:3.11-slim

WORKDIR /app

RUN pip install --no-cache-dir uv

COPY libs/ /app/libs/
COPY services/model_serving/ /app/services/model_serving/

WORKDIR /app/libs

RUN uv pip install --system -e .

WORKDIR /app/services/model_serving

RUN uv pip install --system -e .

WORKDIR /app

ENV PYTHONPATH=/app

EXPOSE 8004

CMD ["uvicorn", "src.main:app", "--host", "0.0.0.0", "--port", "8004"]
