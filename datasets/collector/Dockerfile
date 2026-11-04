FROM python:3.11-slim
WORKDIR /app
RUN apt-get update && apt-get install -y --no-install-recommends git ca-certificates && rm -rf /var/lib/apt/lists/*
COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt
COPY collector.py sources.json README.md ./
RUN mkdir -p /app/data
ENV KTP_DATA_DIR=/app/data PYTHONDONTWRITEBYTECODE=1
ENTRYPOINT ["python", "/app/collector.py"]
CMD ["sources"]
