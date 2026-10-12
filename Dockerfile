FROM node:24-bookworm-slim
WORKDIR /app
COPY package.json package-lock.json ./
RUN npm ci --omit=dev --ignore-scripts
COPY server.mjs billing.mjs recovery.mjs operations.mjs enforcement.mjs credentials.mjs captcha.mjs location.mjs media.mjs ./
COPY geo ./geo
COPY public ./public
COPY scripts ./scripts
ENV HOST=0.0.0.0
ENV DATA_DIR=/data
EXPOSE 3000
CMD ["node", "server.mjs"]
