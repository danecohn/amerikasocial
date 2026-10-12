FROM node:24-bookworm-slim
RUN apt-get update && apt-get install -y --no-install-recommends ffmpeg fonts-dejavu-core fonts-noto-color-emoji && rm -rf /var/lib/apt/lists/*
WORKDIR /app
COPY package.json package-lock.json ./
RUN npm ci --omit=dev --ignore-scripts
COPY server.mjs billing.mjs recovery.mjs operations.mjs enforcement.mjs credentials.mjs captcha.mjs location.mjs media.mjs video.mjs photo.mjs photo-worker.mjs webhooks.mjs mcp.mjs sharing.mjs onboarding.mjs ./
COPY geo ./geo
COPY public ./public
COPY scripts ./scripts
ENV HOST=0.0.0.0
ENV DATA_DIR=/data
EXPOSE 3000
CMD ["node", "server.mjs"]

