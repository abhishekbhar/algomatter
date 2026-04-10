# Deploy AlgoMatter to Production Server

Deploy to the Contabo production server (`194.61.31.226`).

## Server

| IP | Auth | Domain | Notes |
|----|------|--------|-------|
| `194.61.31.226` | Password from `contabo-server.txt` | `algomatter.in` (SSL via Let's Encrypt) | Production |

## Credentials

Read server password from `contabo-server.txt` (one level up from the repo root):

```bash
SERVER_PASS=$(grep '^password:' ../contabo-server.txt | awk '{print $2}')
```

All SSH/rsync commands use `sshpass` via nix (since `sshpass` is not on PATH by default):

```bash
# SSH:
SSHPASS="$SERVER_PASS" nix-shell -p sshpass --run 'sshpass -e ssh -o StrictHostKeyChecking=no root@194.61.31.226 "<command>"'

# Rsync:
SSHPASS="$SERVER_PASS" nix-shell -p sshpass --run 'sshpass -e rsync -avz --progress -e "ssh -o StrictHostKeyChecking=no" <src> root@194.61.31.226:<dst>'

# SCP:
SSHPASS="$SERVER_PASS" nix-shell -p sshpass --run 'sshpass -e scp -o StrictHostKeyChecking=no <src> root@194.61.31.226:<dst>'
```

## Server Architecture
- **PostgreSQL 16 + Redis 7** in Docker (`/opt/algomatter/docker-compose.infra.yml`)
- **FastAPI backend** (uvicorn on port 8000) — `algomatter-api.service`
- **ARQ worker** — `algomatter-worker.service`
- **Strategy runner** — `algomatter-strategy-runner.service`
- **Next.js frontend app** (port 3000, basePath `/app`) — `algomatter-frontend.service`
- **Next.js marketing website** (port 3001, serves `/`) — `algomatter-website.service`
- **Nginx** reverse proxy with SSL for `algomatter.in`

## Argument Handling

- `/deploy` — deploy backend + frontend (default)
- `/deploy backend` — deploy only backend
- `/deploy frontend` — deploy only frontend
- `/deploy website` — deploy only marketing website
- `/deploy all` — deploy backend + frontend + website
- `/deploy full` — full deploy (pip install + npm ci + all)

---

## Deployment Steps

### 0. Read credentials

```bash
SERVER_PASS=$(grep '^password:' ../contabo-server.txt | awk '{print $2}')
```

### 1. Rsync changed files

**Backend:**
```bash
SSHPASS="$SERVER_PASS" nix-shell -p sshpass --run \
  'sshpass -e rsync -avz --progress -e "ssh -o StrictHostKeyChecking=no" \
  --exclude=".venv" --exclude="__pycache__" --exclude=".pytest_cache" \
  --exclude="*.egg-info" --exclude=".env" \
  backend/ root@194.61.31.226:/opt/algomatter/backend/'
```

**Frontend:**
```bash
SSHPASS="$SERVER_PASS" nix-shell -p sshpass --run \
  'sshpass -e rsync -avz --progress -e "ssh -o StrictHostKeyChecking=no" \
  --exclude="node_modules" --exclude=".next" \
  frontend/ root@194.61.31.226:/opt/algomatter/frontend/'
```

**Website (if changed):**
```bash
SSHPASS="$SERVER_PASS" nix-shell -p sshpass --run \
  'sshpass -e rsync -avz --progress -e "ssh -o StrictHostKeyChecking=no" \
  --exclude="node_modules" --exclude=".next" \
  website/ root@194.61.31.226:/opt/algomatter/website/'
```

### 2. Re-apply server-specific patches

**CORS origins** — Add server origins to `backend/app/main.py`:
```bash
SSHPASS="$SERVER_PASS" nix-shell -p sshpass --run \
  'sshpass -e ssh -o StrictHostKeyChecking=no root@194.61.31.226 \
  "sed -i '"'"'/\"http:\/\/127.0.0.1:5173\",/a\\        \"https://algomatter.in\",\n        \"https://www.algomatter.in\",\n        \"http://194.61.31.226\",'"'"' /opt/algomatter/backend/app/main.py"'
```

**CSP connect-src** — Update `frontend/next.config.mjs`:
```bash
SSHPASS="$SERVER_PASS" nix-shell -p sshpass --run \
  'sshpass -e ssh -o StrictHostKeyChecking=no root@194.61.31.226 \
  "sed -i \"s|connect-src '"'"'self'"'"' http://localhost:8000 http://localhost:3000|connect-src '"'"'self'"'"' https://algomatter.in http://194.61.31.226|\" /opt/algomatter/frontend/next.config.mjs"'
```

### 3. Run database migrations
```bash
SSHPASS="$SERVER_PASS" nix-shell -p sshpass --run \
  'sshpass -e ssh -o StrictHostKeyChecking=no root@194.61.31.226 \
  "cd /opt/algomatter/backend && .venv/bin/alembic upgrade head"'
```

### 4. Rebuild frontend
```bash
SSHPASS="$SERVER_PASS" nix-shell -p sshpass --run \
  'sshpass -e ssh -o StrictHostKeyChecking=no root@194.61.31.226 \
  "cd /opt/algomatter/frontend && NODE_OPTIONS=\"--max-old-space-size=512\" NEXT_PUBLIC_API_BASE_URL=\"\" npm run build 2>&1 | tail -5"'
```

If website was updated:
```bash
SSHPASS="$SERVER_PASS" nix-shell -p sshpass --run \
  'sshpass -e ssh -o StrictHostKeyChecking=no root@194.61.31.226 \
  "cd /opt/algomatter/website && NODE_OPTIONS=\"--max-old-space-size=512\" npm run build 2>&1 | tail -5"'
```

### 5. Restart services
```bash
SSHPASS="$SERVER_PASS" nix-shell -p sshpass --run \
  'sshpass -e ssh -o StrictHostKeyChecking=no root@194.61.31.226 \
  "systemctl restart algomatter-api algomatter-worker algomatter-strategy-runner algomatter-frontend"'
```

If website was updated:
```bash
SSHPASS="$SERVER_PASS" nix-shell -p sshpass --run \
  'sshpass -e ssh -o StrictHostKeyChecking=no root@194.61.31.226 \
  "systemctl restart algomatter-website"'
```

### 6. Verify (wait 5-8 seconds for API startup)
```bash
SSHPASS="$SERVER_PASS" nix-shell -p sshpass --run \
  'sshpass -e ssh -o StrictHostKeyChecking=no root@194.61.31.226 \
  "sleep 8 && curl -s https://algomatter.in/api/v1/health && echo \"\" && curl -s -o /dev/null -w \"App: %{http_code}\n\" https://algomatter.in/app && curl -s -o /dev/null -w \"Website: %{http_code}\n\" https://algomatter.in/"'
```

Expected output:
```
{"database":"ok","redis":"ok"}
App: 200
Website: 200
```

### 7. If pip dependencies changed
```bash
SSHPASS="$SERVER_PASS" nix-shell -p sshpass --run \
  'sshpass -e ssh -o StrictHostKeyChecking=no root@194.61.31.226 \
  "cd /opt/algomatter/backend && .venv/bin/pip install --no-cache-dir . 2>&1 | tail -5"'
```

### 8. If npm dependencies changed
```bash
SSHPASS="$SERVER_PASS" nix-shell -p sshpass --run \
  'sshpass -e ssh -o StrictHostKeyChecking=no root@194.61.31.226 \
  "cd /opt/algomatter/frontend && npm ci 2>&1 | tail -5"'
```

## Important Notes

- Run all commands from the **repo root** (`algomatter/`); `contabo-server.txt` is one level up (`../contabo-server.txt`)
- `sshpass` is not on PATH — always use `nix-shell -p sshpass --run` to invoke it
- The API takes ~5-8 seconds to start after restart — always wait before verifying
- Server has limited RAM; frontend builds use `--max-old-space-size=512`
- Backend `.env` on the server has its own secrets — never overwrite it (excluded from rsync)
- SSL via Let's Encrypt, auto-renews via certbot
