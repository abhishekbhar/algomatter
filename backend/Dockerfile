FROM python:3.12-slim AS base
WORKDIR /app

FROM base AS deps
COPY pyproject.toml .
RUN pip install --no-cache-dir .

FROM deps AS app
COPY . .
ENV PYTHONPATH=/app
EXPOSE 8000
CMD ["sh", "-c", "alembic upgrade head && uvicorn app.main:app --host 0.0.0.0 --port 8000"]
