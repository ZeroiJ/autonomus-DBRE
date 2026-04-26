FROM python:3.10-slim
WORKDIR /app
RUN apt-get update && apt-get install -y postgresql postgresql-client libpq-dev gcc && rm -rf /var/lib/apt/lists/*
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY . .
EXPOSE 8000 7860
CMD ["sh", "-c", "\
    service postgresql start && \
    su - postgres -c \"psql -c \\\"CREATE USER dbre_admin WITH PASSWORD 'dbre_pass';\\\"\" 2>/dev/null; \
    su - postgres -c \"psql -c 'CREATE DATABASE dbre OWNER dbre_admin;'\" 2>/dev/null; \
    su - postgres -c \"psql -c 'GRANT ALL ON DATABASE dbre TO dbre_admin;'\" 2>/dev/null; \
    export DB_USER=dbre_admin DB_PASSWORD=dbre_pass DB_NAME=dbre DB_HOST=localhost DB_PORT=5432; \
    uvicorn server.app:app --host 0.0.0.0 --port 8000 & \
    python3 app.py"]
