FROM python:3.10-slim
WORKDIR /app
RUN apt-get update && apt-get install -y postgresql-client libpq-dev gcc
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY . .
EXPOSE 8000 7860
CMD ["sh", "-c", "uvicorn server.app:app --host 0.0.0.0 --port 8000 & python app.py"]
