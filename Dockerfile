## One Touch Audit — API container (repo root)
##
## This repo already contains per-app Dockerfiles:
## - apps/backend/Dockerfile (build context: apps/; Easypanel: Build path apps, File backend/Dockerfile)
## - apps/frontend/Dockerfile (build context: apps/; Easypanel: Build path apps, File frontend/Dockerfile)
##
## This root Dockerfile exists so `docker build .` works out of the box
## (e.g. for platforms that expect a Dockerfile at the repository root).
##
## Build:
##   docker build -t onetouch-audit-ai-api .
## Run:
##   docker run --rm -p 8000:8000 -e MONGO_URL="mongodb://host.docker.internal:27017" onetouch-audit-ai-api

FROM python:3.11-slim

WORKDIR /app

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PYTHONPATH=/app \
    PIP_PREFER_BINARY=1

COPY apps/backend/requirements.txt ./requirements.txt
RUN pip install --extra-index-url https://d33sy5i8bnduwe.cloudfront.net/simple/ -r requirements.txt

COPY apps/backend/ ./

# Compatibility for integration tests that read /app/frontend/.env inside the api container.
RUN mkdir -p /app/frontend && printf "REACT_APP_BACKEND_URL=http://127.0.0.1:8000\n" > /app/frontend/.env

EXPOSE 8000

CMD ["uvicorn", "server:app", "--host", "0.0.0.0", "--port", "8000"]

