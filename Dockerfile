# Storefront Concierge — Node web/API server + Python LangGraph agent in one image.
FROM node:20-slim

ENV PYTHONUNBUFFERED=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    PIP_NO_CACHE_DIR=1 \
    PORT=3000

RUN apt-get update \
 && apt-get install -y --no-install-recommends python3 python3-pip python3-venv ca-certificates \
 && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Install Python deps first for better layer caching.
COPY agent/requirements.txt agent/requirements.txt
RUN python3 -m venv /opt/venv \
 && /opt/venv/bin/pip install -r agent/requirements.txt
ENV PATH="/opt/venv/bin:${PATH}"

# Node has no runtime deps yet, but copy package.json so future deps install cleanly.
COPY package.json ./
RUN if [ -f package-lock.json ]; then npm ci --omit=dev; else npm install --omit=dev; fi

# Copy the rest of the app.
COPY . .

EXPOSE 3000

HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
  CMD node -e "fetch('http://127.0.0.1:'+(process.env.PORT||3000)+'/health').then(r=>{process.exit(r.ok?0:1)}).catch(()=>process.exit(1))"

CMD ["node", "server.js"]
