# Check Server Status

Check the status of all AlgoMatter services on the production server at `194.61.31.226`.

## Steps

### 1. Check all services
```bash
ssh -i ~/.ssh/id_ed25519 -o StrictHostKeyChecking=no root@194.61.31.226 'systemctl status algomatter-api algomatter-worker algomatter-strategy-runner algomatter-frontend algomatter-website --no-pager 2>&1 | grep -E "●|Active:"'
```

### 2. Check Docker infra
```bash
ssh -i ~/.ssh/id_ed25519 -o StrictHostKeyChecking=no root@194.61.31.226 'cd /opt/algomatter && docker compose -f docker-compose.infra.yml ps'
```

### 3. Check health endpoint
```bash
ssh -i ~/.ssh/id_ed25519 -o StrictHostKeyChecking=no root@194.61.31.226 'curl -s https://algomatter.in/api/v1/health'
```

### 4. Check memory usage
```bash
ssh -i ~/.ssh/id_ed25519 -o StrictHostKeyChecking=no root@194.61.31.226 'free -h | head -2'
```

### 5. Check recent API logs (if there are issues)
```bash
ssh -i ~/.ssh/id_ed25519 -o StrictHostKeyChecking=no root@194.61.31.226 'journalctl -u algomatter-api --no-pager -n 20'
```

Report the results in a concise table format.
