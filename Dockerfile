FROM python:3.12-slim

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends \
    tzdata \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

RUN mkdir -p /data /app/logs

ENV PYTHONUNBUFFERED=1
ENV DATABASE_PATH=/data/sales.db

CMD ["python", "bot.py"]
