# One Touch Audit — production static bundle
FROM node:20-alpine AS build

WORKDIR /app

# Install deps (cached when lockfiles unchanged)
COPY apps/frontend/package.json apps/frontend/yarn.lock ./
RUN corepack enable && yarn install --frozen-lockfile --network-timeout 600000 --prefer-offline

# App sources (respects .dockerignore)
COPY apps/frontend/ ./

ARG REACT_APP_BACKEND_URL=
ENV REACT_APP_BACKEND_URL=$REACT_APP_BACKEND_URL
ENV NODE_ENV=production
ENV CI=false
ENV GENERATE_SOURCEMAP=false
ENV NODE_OPTIONS=--max_old_space_size=4096
RUN yarn build

FROM nginx:1.27-alpine

COPY infra/docker/nginx.conf /etc/nginx/conf.d/default.conf
COPY --from=build /app/build /usr/share/nginx/html

EXPOSE 80

HEALTHCHECK --interval=30s --timeout=3s --retries=3 \
  CMD wget -qO- http://127.0.0.1/ >/dev/null || exit 1

CMD ["nginx", "-g", "daemon off;"]
