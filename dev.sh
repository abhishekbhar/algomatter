#!/usr/bin/env bash
set -e

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"

cleanup() {
    echo "Stopping services..."
    kill $WEBSITE_PID $FRONTEND_PID $NGINX_PID 2>/dev/null || true
    wait $WEBSITE_PID $FRONTEND_PID 2>/dev/null || true
    nginx -s stop -c "$SCRIPT_DIR/nginx.conf" 2>/dev/null || true
    echo "All services stopped."
}
trap cleanup EXIT INT TERM

echo "Starting Algomatter dev environment..."

# Kill anything on ports 3000-3002
for port in 3000 3001 3002; do
    lsof -ti :$port 2>/dev/null | xargs kill -9 2>/dev/null || true
done
sleep 1

# Start frontend app on port 3001
echo "Starting frontend app on :3001..."
cd "$SCRIPT_DIR/frontend"
nix develop "$SCRIPT_DIR" --command bash -c "npm run dev -- --port 3001" &
FRONTEND_PID=$!

# Start marketing website on port 3002
echo "Starting marketing website on :3002..."
cd "$SCRIPT_DIR/website"
nix develop "$SCRIPT_DIR" --command bash -c "npm run dev -- --port 3002" &
WEBSITE_PID=$!

# Wait for both Next.js servers to start
echo "Waiting for Next.js servers..."
sleep 5

# Start nginx on port 3000
echo "Starting nginx on :3000..."
nginx -c "$SCRIPT_DIR/nginx.conf"
NGINX_PID=$!

echo ""
echo "============================================"
echo "  Algomatter dev environment running"
echo "============================================"
echo "  http://localhost:3000        — unified URL"
echo "  http://localhost:3000/app    — frontend app"
echo "  http://localhost:3002        — website direct"
echo "  http://localhost:3001/app    — frontend direct"
echo "============================================"
echo ""
echo "Press Ctrl+C to stop all services."

wait
