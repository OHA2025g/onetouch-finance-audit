# One Touch Audit — production static bundle (build context: apps/frontend)
FROM node:20-alpine AS build

WORKDIR /app

# Install deps (cached when lockfiles unchanged)
COPY package.json yarn.lock ./
ENV YARN_CACHE_FOLDER=/usr/local/share/.cache/yarn
RUN corepack enable && \
    yarn install --frozen-lockfile --network-timeout 600000 --check-files --prefer-offline

# App sources (respects .dockerignore)
COPY . .

# Empty = same-origin /api (dev proxy) or platform-level routing (e.g. Easypanel).
# For local docker compose without nginx /api proxy, pass the host-reachable API URL.
ARG REACT_APP_BACKEND_URL=
ENV REACT_APP_BACKEND_URL=$REACT_APP_BACKEND_URL
ENV NODE_ENV=production
ENV CI=false
ENV GENERATE_SOURCEMAP=false
ENV NODE_OPTIONS=--max_old_space_size=4096

RUN yarn build

FROM nginx:1.27-alpine

COPY docker/nginx.conf /etc/nginx/conf.d/default.conf
COPY --from=build /app/build /usr/share/nginx/html

EXPOSE 80

HEALTHCHECK --interval=30s --timeout=3s --retries=3 \
  CMD wget -qO- http://127.0.0.1/ >/dev/null || exit 1

CMD ["nginx", "-g", "daemon off;"]
