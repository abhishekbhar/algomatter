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

## Authentication

Server uses **password auth** (no SSH key). Use paramiko via the backend venv:

```bash
source /home/abhishekbhar/projects/algomatter_worktree/algomatter/backend/.venv/bin/activate
```

Credentials in `/home/abhishekbhar/projects/algomatter_worktree/contabo-server.txt`.

## Python command (use this — sshpass not available)

For a single service (replace `<service-name>` and adjust `-n` as needed):

```python
import paramiko
client = paramiko.SSHClient()
client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
client.connect('194.61.31.226', username='root', password='IDilXKY3NvaQXQFa6NWyB475OeH3', timeout=15)
stdin, stdout, stderr = client.exec_command('journalctl -u <service-name> --no-pager -n 30')
print(stdout.read().decode())
client.close()
```

For nginx:
```python
stdin, stdout, stderr = client.exec_command('tail -30 /var/log/nginx/error.log')
```

For `all`, run each service with `-n 10` and label output.

## Full bash invocation pattern

```bash
source /home/abhishekbhar/projects/algomatter_worktree/algomatter/backend/.venv/bin/activate && python3 - <<'EOF'
import paramiko
client = paramiko.SSHClient()
client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
client.connect('194.61.31.226', username='root', password='IDilXKY3NvaQXQFa6NWyB475OeH3', timeout=15)
stdin, stdout, stderr = client.exec_command('journalctl -u algomatter-api --no-pager -n 30')
print(stdout.read().decode())
client.close()
EOF
```
