FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

WORKDIR /app

COPY requirements.txt .

RUN pip install --no-cache-dir -r requirements.txt \
    && addgroup --system appuser \
    && adduser --system --ingroup appuser appuser

COPY . .

RUN mkdir -p /app/data/day02 \
    && chown -R appuser:appuser /app

USER appuser

EXPOSE 8000

CMD ["python", "-m", "uvicorn", "projects.ai_metrics_api.main:app", "--host", "0.0.0.0", "--port", "8000"]
