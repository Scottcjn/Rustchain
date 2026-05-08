FROM python:3.10-slim

WORKDIR /app

COPY --chown=appuser:appuser requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY --chown=appuser:appuser . .

RUN adduser --disabled-password --gecos '' appuser
USER appuser

CMD ["python", "bot.py"]
