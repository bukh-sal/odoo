FROM python:3.12-slim-bookworm@sha256:6dd8b6dab6b3adc7812bab69eca5dbdc1a5cc690ad28306d234ffb4ef8ac9753 AS builder
ENV PIP_DISABLE_PIP_VERSION_CHECK=1 PIP_NO_CACHE_DIR=1 PYTHONDONTWRITEBYTECODE=1
COPY services/document_stats/requirements.lock /locks/requirements.lock
RUN python -m venv /venv && /venv/bin/python -m pip install --only-binary=:all: --require-hashes -r /locks/requirements.lock && /venv/bin/python -m pip check

FROM python:3.12-slim-bookworm@sha256:6dd8b6dab6b3adc7812bab69eca5dbdc1a5cc690ad28306d234ffb4ef8ac9753
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 PYTHONPATH=/app/packages/platform_sdk:/app
COPY --from=builder /venv /venv
WORKDIR /app
COPY services/document_stats/__init__.py services/document_stats/engine.py services/document_stats/server.py /app/services/document_stats/
COPY packages/platform_sdk/modular_platform/__init__.py packages/platform_sdk/modular_platform/contracts.py packages/platform_sdk/modular_platform/tokens.py /app/packages/platform_sdk/modular_platform/
COPY packages/contracts/v1/worker-request.schema.json packages/contracts/v1/worker-response.schema.json packages/contracts/v1/worker-claims.schema.json /app/packages/contracts/v1/
COPY services/document_stats/requirements.lock services/document_stats/dependency-provenance.json /app/provenance/
COPY LICENSE COPYRIGHT /app/provenance/
USER 10002:10002
EXPOSE 8080
ENTRYPOINT ["/venv/bin/python","-m","services.document_stats.server"]
CMD ["--config","/run/worker/config.json","--host","0.0.0.0","--port","8080"]
