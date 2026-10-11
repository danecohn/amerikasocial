FROM node:24-bookworm-slim
WORKDIR /app
COPY package.json package-lock.json ./
RUN npm ci --omit=dev --ignore-scripts
COPY server.mjs billing.mjs ./
COPY public ./public
ENV HOST=0.0.0.0
ENV DATA_DIR=/data
EXPOSE 3000
CMD ["node", "server.mjs"]
