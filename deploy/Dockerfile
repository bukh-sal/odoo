# syntax=docker/dockerfile:1
ARG PYTHON_IMAGE=python:3.12-slim-bookworm@sha256:6dd8b6dab6b3adc7812bab69eca5dbdc1a5cc690ad28306d234ffb4ef8ac9753
FROM ${PYTHON_IMAGE} AS builder
ARG DEBIAN_SNAPSHOT=20261027T000000Z
ENV PIP_DISABLE_PIP_VERSION_CHECK=1 PIP_NO_CACHE_DIR=1 PYTHONDONTWRITEBYTECODE=1
RUN printf 'deb [check-valid-until=no] https://snapshot.debian.org/archive/debian/%s/ bookworm main\ndeb [check-valid-until=no] https://snapshot.debian.org/archive/debian-security/%s/ bookworm-security main\n' "$DEBIAN_SNAPSHOT" "$DEBIAN_SNAPSHOT" > /etc/apt/sources.list \
    && rm /etc/apt/sources.list.d/debian.sources \
    && apt-get update \
    && apt-get install -y --no-install-recommends build-essential libldap2-dev libsasl2-dev libpq-dev libssl-dev libffi-dev \
    && rm -rf /var/lib/apt/lists/*
COPY deploy/build-requirements.lock /locks/build-requirements.lock
COPY deploy/requirements-py312.lock /locks/requirements.lock
RUN python -m pip install --require-hashes -r /locks/build-requirements.lock \
    && python -m venv /venv \
    && /venv/bin/python -m pip install --require-hashes -r /locks/build-requirements.lock \
    && /venv/bin/python -m pip install --no-build-isolation --require-hashes -r /locks/requirements.lock \
    && /venv/bin/python -m pip check
COPY . /source
RUN python /source/tools/build_distribution.py /source /release

FROM ${PYTHON_IMAGE} AS runtime
ARG DEBIAN_SNAPSHOT=20261027T000000Z
ENV PATH=/venv/bin:$PATH PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 LANG=C.UTF-8
RUN printf 'deb [check-valid-until=no] https://snapshot.debian.org/archive/debian/%s/ bookworm main\ndeb [check-valid-until=no] https://snapshot.debian.org/archive/debian-security/%s/ bookworm-security main\n' "$DEBIAN_SNAPSHOT" "$DEBIAN_SNAPSHOT" > /etc/apt/sources.list \
    && rm /etc/apt/sources.list.d/debian.sources \
    && apt-get update \
    && apt-get install -y --no-install-recommends libldap-2.5-0 libsasl2-2 libpq5 libmagic1 fonts-dejavu-core fonts-liberation \
    && rm -rf /var/lib/apt/lists/* \
    && groupadd --gid 10001 modular && useradd --uid 10001 --gid modular --create-home modular \
    && mkdir -p /var/lib/modular && chown modular:modular /var/lib/modular
COPY --from=builder /venv /venv
COPY --from=builder /release /opt/modular
COPY tools /opt/modular/tools
COPY deploy/requirements-py312.lock /opt/modular/requirements.lock
COPY tests/fixtures/addons /opt/modular/fixtures
WORKDIR /opt/modular
USER 10001:10001
EXPOSE 8069
ENTRYPOINT ["python", "odoo-bin"]
CMD ["-c", "/run/secrets/odoo_config"]
