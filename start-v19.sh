#!/bin/sh
set -eu

echo "[WithHina] Starting private PO Token provider on 127.0.0.1:4416..."
cd /opt/bgutil-provider/server
node build/main.js --host 127.0.0.1 --port 4416 &
POT_PID=$!

cleanup() {
  kill "$POT_PID" 2>/dev/null || true
}
trap cleanup EXIT INT TERM

echo "[WithHina] Waiting for PO Token provider..."
python3 - <<'PY'
import time, urllib.request
url = "http://127.0.0.1:4416/"
for _ in range(40):
    try:
        urllib.request.urlopen(url, timeout=1)
        print("[WithHina] PO Token provider is reachable.")
        break
    except Exception:
        time.sleep(0.5)
else:
    raise SystemExit("[WithHina] PO Token provider did not start.")
PY

cd /app/backend
exec uvicorn app:app --host 0.0.0.0 --port "${PORT:-10000}"
