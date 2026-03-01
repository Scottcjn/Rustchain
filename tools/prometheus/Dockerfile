FROM python:3.11-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY rustchain_exporter.py .

ENV RUSTCHAIN_NODE_URL=http://localhost:8080
ENV EXPORTER_PORT=9100
ENV SCRAPE_INTERVAL=60

EXPOSE 9100

CMD ["python3", "rustchain_exporter.py"]
