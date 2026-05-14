FROM python:3.10-slim

WORKDIR /app

# Install libpq-dev (psycopg2 runtime) + gcc (compilation), then purge gcc after pip install
COPY requirements.txt .
RUN apt-get update \
    && apt-get install -y --no-install-recommends libpq-dev gcc \
    && pip install --no-cache-dir -r requirements.txt \
    && apt-get purge -y gcc \
    && apt-get autoremove -y \
    && rm -rf /var/lib/apt/lists/*

COPY . .

COPY entrypoint.sh /entrypoint.sh
RUN sed -i 's/\r$//' /entrypoint.sh && chmod +x /entrypoint.sh

EXPOSE 8000

ENTRYPOINT ["/entrypoint.sh"]
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000", "--log-level", "info"]
