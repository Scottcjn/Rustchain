FROM python:3.11-slim

WORKDIR /app

# Install dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy bot code
COPY . .

# Run as non-root user
RUN useradd -m -u 1000 botuser
USER botuser

CMD ["python", "bot.py"]
