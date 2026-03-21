FROM python:3.11-slim

WORKDIR /app

RUN pip install --no-cache-dir uv

COPY libs/ /app/libs/
COPY services/biometric_service/ /app/services/biometric_service/

WORKDIR /app/libs

RUN uv pip install --system -e .

WORKDIR /app/services/biometric_service

RUN uv pip install --system -e .

WORKDIR /app

ENV PYTHONPATH=/app

EXPOSE 8003

CMD ["uvicorn", "src.main:app", "--host", "0.0.0.0", "--port", "8003"]
