FROM python:3.10-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY rustchain_exporter.py .

EXPOSE 9100

CMD ["python", "rustchain_exporter.py"]
