FROM node:22-bookworm-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    POT_PROVIDER_URL=http://127.0.0.1:4416

RUN apt-get update && apt-get install -y --no-install-recommends \
    python3 python3-venv python3-pip git ca-certificates ffmpeg \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /opt

RUN git clone --depth 1 --branch 1.3.2 \
    https://github.com/Brainicism/bgutil-ytdlp-pot-provider.git /opt/bgutil-provider \
    && cd /opt/bgutil-provider/server \
    && npm ci \
    && npx tsc

WORKDIR /app
COPY backend/requirements.txt /app/backend/requirements.txt

RUN python3 -m venv /opt/venv \
    && /opt/venv/bin/pip install --no-cache-dir --upgrade pip \
    && /opt/venv/bin/pip install --no-cache-dir -r /app/backend/requirements.txt

COPY backend /app/backend
COPY start-v19.sh /app/start-v19.sh
RUN chmod +x /app/start-v19.sh

ENV PATH="/opt/venv/bin:$PATH"

CMD ["/app/start-v19.sh"]
