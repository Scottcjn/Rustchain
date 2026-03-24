FROM python:3.12-slim
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY . .
EXPOSE 5580
CMD ["gunicorn", "-w", "2", "-b", "0.0.0.0:5580", "otc_bridge:app"]
