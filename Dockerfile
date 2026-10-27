FROM node:24-bookworm-slim
RUN apt-get update && apt-get install -y --no-install-recommends ffmpeg fontconfig fonts-dejavu-core fonts-noto-color-emoji && rm -rf /var/lib/apt/lists/*
WORKDIR /app
LABEL org.opencontainers.image.licenses="GPL-3.0-or-later"
COPY LICENSE ./LICENSE
COPY package.json package-lock.json ./
RUN npm ci --omit=dev --ignore-scripts
COPY assets-gallery.mjs brand.mjs identity.mjs search-proxy.mjs search-preferences.mjs countries.json apt-repository.mjs software-downloads.mjs software-release-catalog.mjs gaming-mcp.mjs account-designations.mjs gaming.mjs gaming-originals.json google-billing.mjs desktop-auth.mjs account-safety.mjs push.mjs apple-billing.mjs server.mjs mcp-events.mjs login-guard.mjs billing.mjs recovery.mjs operations.mjs enforcement.mjs credentials.mjs captcha.mjs location.mjs media.mjs video.mjs photo.mjs photo-worker.mjs webhooks.mjs mcp.mjs oauth.mjs dating.mjs communities.mjs boosts.mjs moderation.mjs sharing.mjs onboarding.mjs ./
COPY apt-repo ./apt-repo
COPY certificates ./certificates
COPY geo ./geo
COPY public ./public
COPY public/brand/vigiltech/fonts/*.ttf /usr/local/share/fonts/vigiltech/
RUN fc-cache -f
COPY scripts ./scripts
ENV HOST=0.0.0.0
ENV DATA_DIR=/data
EXPOSE 3000
CMD ["node", "server.mjs"]

