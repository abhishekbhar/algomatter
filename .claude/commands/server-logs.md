# View Server Logs

View logs for AlgoMatter services on the production server at `194.61.31.226`.

## Usage

- `/server-logs` — show last 30 lines of API logs
- `/server-logs api` — API service logs
- `/server-logs worker` — ARQ worker logs
- `/server-logs runner` — Strategy runner logs
- `/server-logs frontend` — Frontend logs
- `/server-logs website` — Marketing website logs
- `/server-logs nginx` — Nginx access/error logs
- `/server-logs all` — last 10 lines of each service

## Commands

Map the argument to the service name:
- `api` → `algomatter-api`
- `worker` → `algomatter-worker`
- `runner` → `algomatter-strategy-runner`
- `frontend` → `algomatter-frontend`
- `website` → `algomatter-website`

```bash
ssh -i ~/.ssh/id_ed25519 -o StrictHostKeyChecking=no root@194.61.31.226 'journalctl -u <service-name> --no-pager -n 30'
```

For nginx:
```bash
ssh -i ~/.ssh/id_ed25519 -o StrictHostKeyChecking=no root@194.61.31.226 'tail -30 /var/log/nginx/error.log'
```

For `all`, run each with `-n 10` and label the output.
