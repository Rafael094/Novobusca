# =============================================================================
# IntelliINPI — imagem do WORKER de ingestão (pePI / dados abertos)
#
# Contexto de build = ./ingestion (o pipeline é autônomo; NÃO usa o pacote
# `app` do backend). Diferente da imagem da API, aqui o pacote `ingestion`
# entra de verdade, então `python -m ingestion.<cmd>` funciona.
#
# Usada pelo serviço `peticoes` do docker-compose.prod.yml. Como o pipeline lê
# a configuração de variáveis de ambiente quando `app.config` não está
# importável (ver ingestion/config.py), basta passar DATABASE_URL/DATA_DIR via
# env_file — os mesmos do backend/.env.
# =============================================================================
FROM python:3.13-slim

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1

# libpq é exigida em runtime pelo psycopg; ca-certificates para o TLS do pePI.
RUN apt-get update \
    && apt-get install -y --no-install-recommends libpq5 ca-certificates \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Dependências primeiro (melhor cache de camada).
COPY requirements.txt ./ingestion-requirements.txt
RUN pip install --upgrade pip \
    && pip install -r ./ingestion-requirements.txt

# O pacote em si, importável como `ingestion.*`.
COPY . /app/ingestion

# Comando padrão só valida a conectividade com o pePI; o serviço sobrescreve.
CMD ["python", "-m", "ingestion.peticoes", "--diagnostico"]
