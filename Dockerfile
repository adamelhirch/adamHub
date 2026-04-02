FROM node:22-alpine AS web-builder

WORKDIR /web

ARG VITE_API_URL
ARG VITE_API_KEY

ENV VITE_API_URL=${VITE_API_URL}
ENV VITE_API_KEY=${VITE_API_KEY}

COPY web/package.json web/package-lock.json ./
RUN npm ci

COPY web/ ./
RUN npm run build


FROM python:3.12-slim AS runtime

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

WORKDIR /app

RUN apt-get update \
    && apt-get install -y --no-install-recommends ffmpeg libgomp1 \
    && rm -rf /var/lib/apt/lists/*

COPY pyproject.toml README.md alembic.ini ./
COPY app ./app
COPY alembic ./alembic
COPY data/cookies_intermarche.json ./data/cookies_intermarche.json

RUN pip install --no-cache-dir . \
    && python -m camoufox fetch

COPY --from=web-builder /web/dist ./web/dist
COPY scripts/docker-entrypoint.sh /docker-entrypoint.sh

RUN chmod +x /docker-entrypoint.sh

EXPOSE 8000

ENTRYPOINT ["/docker-entrypoint.sh"]
