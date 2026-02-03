# syntax=docker/dockerfile:1
FROM python:3.11-slim

WORKDIR /app

RUN useradd --create-home --shell /bin/bash appuser

COPY requirements.txt .
RUN --mount=type=cache,target=/root/.cache/pip pip install -r requirements.txt

COPY --chown=appuser:appuser . .
RUN mkdir -p /app/data/raw/projects /app/data/raw/commits /app/data/processed && chown -R appuser:appuser /app/data

USER appuser

ENV PYTHONUNBUFFERED=1
EXPOSE 8501

CMD ["streamlit", "run", "app.py", "--server.port=8501", "--server.address=0.0.0.0"]
