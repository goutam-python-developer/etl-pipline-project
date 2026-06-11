# Week 4 - Day 6-7: Docker containerization
FROM python:3.11-slim

WORKDIR /app

RUN apt-get update && apt-get install -y \
    gcc g++ libpq-dev curl \
    && apt-get clean && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir -r requirements.txt

COPY . .

RUN useradd -m -u 1000 etluser && chown -R etluser:etluser /app
USER etluser

ENV PYTHONPATH=/app
ENV LOG_LEVEL=INFO

CMD ["python", "orchestration/pipeline.py"]
