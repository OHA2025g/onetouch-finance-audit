# Clean “all-in-one” image:
# - builds React frontend
# - runs FastAPI backend (uvicorn) on 127.0.0.1:8000
# - runs nginx on :5175 serving the frontend and proxying /api -> backend

FROM node:20-alpine AS web_build
WORKDIR /app
COPY apps/frontend/package.json apps/frontend/yarn.lock ./
RUN corepack enable && yarn install --network-timeout 600000
COPY apps/frontend/ ./
ENV NODE_ENV=production
ENV CI=false
ENV GENERATE_SOURCEMAP=false
ENV NODE_OPTIONS=--max_old_space_size=4096
RUN yarn build

FROM python:3.11-slim AS api_build
WORKDIR /app
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PYTHONPATH=/app
COPY apps/backend/requirements.txt ./requirements.txt
RUN pip install --no-cache-dir --extra-index-url https://d33sy5i8bnduwe.cloudfront.net/simple/ -r requirements.txt
COPY apps/backend/ ./

FROM python:3.11-slim
WORKDIR /app

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PYTHONPATH=/app

RUN apt-get update \
  && apt-get install -y --no-install-recommends nginx ca-certificates curl \
  && rm -rf /var/lib/apt/lists/*

# Python dependencies (uvicorn, fastapi, etc.)
COPY --from=api_build /usr/local /usr/local

# Backend
COPY --from=api_build /app /app

# Frontend static
COPY --from=web_build /app/build /usr/share/nginx/html
COPY infra/clean/nginx.conf /etc/nginx/conf.d/default.conf
COPY infra/clean/start.sh /start.sh
RUN chmod +x /start.sh

EXPOSE 5175

CMD ["/start.sh"]

