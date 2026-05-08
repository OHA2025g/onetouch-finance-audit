FROM python:3.11-slim

WORKDIR /app

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PYTHONPATH=/app

COPY apps/backend/requirements.txt ./requirements.txt
RUN pip install --extra-index-url https://d33sy5i8bnduwe.cloudfront.net/simple/ -r requirements.txt

COPY apps/backend/ ./

# Compatibility for integration tests that read /app/frontend/.env inside the api container.
# Point them at the API service directly to avoid nginx startup timing.
RUN mkdir -p /app/frontend && printf "REACT_APP_BACKEND_URL=http://127.0.0.1:8000\n" > /app/frontend/.env

EXPOSE 8000

CMD ["uvicorn", "server:app", "--host", "0.0.0.0", "--port", "8000"]

