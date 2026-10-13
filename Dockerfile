FROM python:3.12-slim

# Boas praticas: sem .pyc, saida sem buffer, sem cache do pip.
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1 \
    PORT=3000 \
    DB_PATH=/data/database.db

WORKDIR /app

# Dependencias primeiro (aproveita o cache de camadas do Docker).
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

# Usuario sem privilegios + pasta de dados (volume) para o SQLite.
RUN useradd --create-home --uid 10001 appuser \
    && mkdir -p /data \
    && chown -R appuser:appuser /app /data
USER appuser

EXPOSE 3000

# Healthcheck contra /api/health (o orquestrador reinicia o container se cair).
HEALTHCHECK --interval=30s --timeout=5s --start-period=15s --retries=3 \
    CMD python -c "import urllib.request,sys; sys.exit(0 if urllib.request.urlopen('http://127.0.0.1:3000/api/health', timeout=3).status == 200 else 1)"

CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "3000"]
