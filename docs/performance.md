# AlgoMatter — Performance & Capacity

_Last updated: 2026-04-10_

---

## Production Server

| Resource | Value |
|----------|-------|
| Host | Contabo VPS — `194.61.31.226` |
| CPU | 8-core AMD EPYC |
| RAM | 23 GB |
| Disk | 387 GB SSD |
| Swap | 4 GB (`/swapfile`, persisted in `/etc/fstab`) |
| OS | Linux (systemd) |

---

## Service Configuration

### API — `algomatter-api.service`

```ini
ExecStart=uvicorn app.main:app --host 127.0.0.1 --port 8000 --workers 4
```

- 4 worker processes (1 master + 4 async workers)
- Each worker runs a full async FastAPI app with its own connection pool
- Total DB connections in use: `4 workers × pool_size=20 = 80` (out of 200 max)

### Database — PostgreSQL 16

```yaml
# docker-compose.infra.yml
command: postgres -c max_connections=200 -c shared_buffers=256MB
deploy:
  resources:
    limits:
      memory: 512M
```

| Setting | Value | Notes |
|---------|-------|-------|
| `max_connections` | 200 | Up from 100. Headroom: 120 reserved, 80 used by API workers |
| `shared_buffers` | 256 MB | Up from 128 MB. Caches frequently accessed pages |
| Memory limit | 512 MB | Up from 256 MB |

### Redis 7

```yaml
deploy:
  resources:
    limits:
      memory: 128M
```

| Setting | Value |
|---------|-------|
| `maxclients` | 10,000 (default) |
| Memory limit | 128 MB (up from 64 MB) |
| Role | Rate limiter, ARQ job queue, session cache |

### SQLAlchemy Connection Pool

```python
# backend/app/db/session.py
engine = create_async_engine(settings.database_url, pool_size=20)
```

Each of the 4 uvicorn workers maintains its own pool of 20 connections.

---

## Rate Limits

| Endpoint | Limit | Key |
|----------|-------|-----|
| Webhook ingest (`/api/v1/webhook/*`) | 60 req/min | Per webhook token |
| Login / Signup / Refresh | 20 req/min | Per client IP |
| All other endpoints | Unlimited | — |

Configured in `backend/app/middleware/rate_limiter.py`.

---

## Capacity Estimates

These are practical estimates based on current configuration and typical request latency (15–30 ms per API call).

| Metric | Estimate | Bottleneck |
|--------|----------|------------|
| Concurrent dashboard users | ~200–300 | Uvicorn workers |
| Webhook signals/sec (sustained) | ~120–200/sec | DB write throughput |
| Paper trades/sec | ~180/sec | DB transactions |
| Live broker orders/sec | ~20–30/sec | ARQ single worker (sequential) |
| Webhook signals stored (before index degrades) | ~1–2 million rows | `ix_webhook_signals_tenant_received` index |

### Assumptions
- Average API response time: 15–30 ms
- 4 async uvicorn workers, each handling ~50 concurrent connections
- Paper trade = 3 DB operations at ~3 ms each
- Live orders processed sequentially by the single ARQ worker

---

## Known Bottlenecks

| Component | Issue | Impact |
|-----------|-------|--------|
| **ARQ worker** | Single process; processes jobs sequentially | Live orders queue up under load |
| **No PgBouncer** | Direct connections from app pool to Postgres | Scaling beyond 4→8 workers would approach the 200-connection limit |
| **No CDN** | Static assets served directly from Nginx | Adds latency for geographically distant users |
| **Backtest jobs** | CPU-bound; blocks the ARQ worker while running | Delays other background jobs (live orders) during backtests |

---

## Scaling Path

When limits are approached, apply changes in this order:

1. **Scale ARQ to 2 workers** — handles live orders + backtest jobs in parallel
   ```ini
   ExecStart=arq worker.WorkerSettings --workers 2
   ```

2. **Add PgBouncer** — transaction-mode pooling allows 8+ uvicorn workers without hitting Postgres connection limit

3. **Scale uvicorn to 8 workers** — fully utilises all 8 CPU cores (requires PgBouncer first)

4. **Separate backtest worker** — dedicate one ARQ worker to backtest jobs, another to live order execution

5. **Upgrade Postgres `shared_buffers` to 512 MB** — safe up to 25% of total RAM

---

## Monitoring Checklist

Run these commands to spot issues before they become outages:

```bash
# Memory pressure
free -h

# Swap usage (should stay near 0 under normal load)
swapon --show

# Active DB connections (should stay well below 200)
docker exec algomatter-postgres-1 psql -U algomatter algomatter \
  -c "SELECT count(*) FROM pg_stat_activity;"

# Redis memory
docker exec algomatter-redis-1 redis-cli INFO memory | grep used_memory_human

# Uvicorn worker count (should be 5: 1 master + 4 workers)
pgrep -c -P $(pgrep -f "uvicorn.*workers")

# API health
curl -s https://algomatter.in/api/v1/health
```

---

## Change History

| Date | Change | Reason |
|------|--------|--------|
| 2026-04-10 | Uvicorn workers: 1 → 4 | ~4× throughput; 8-core server was idle |
| 2026-04-10 | Postgres `max_connections`: 100 → 200 | Headroom for additional workers |
| 2026-04-10 | Postgres `shared_buffers`: 128 MB → 256 MB | Better page cache hit rate |
| 2026-04-10 | Postgres memory limit: 256 MB → 512 MB | Support increased `shared_buffers` |
| 2026-04-10 | Redis memory limit: 64 MB → 128 MB | Headroom for rate-limit keys at scale |
| 2026-04-10 | Added 4 GB swap (`/swapfile`) | Prevent OOM kills during backtest spikes |
