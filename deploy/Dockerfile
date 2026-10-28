# syntax=docker/dockerfile:1@sha256:4edf897a3ffa55b89f906fc8cc78afdb3f1834cc9c7083565e611a8a7d5fe99e
ARG PYTHON_IMAGE=python:3.12-slim-bookworm@sha256:6dd8b6dab6b3adc7812bab69eca5dbdc1a5cc690ad28306d234ffb4ef8ac9753
FROM ${PYTHON_IMAGE} AS builder
ARG DISTRIBUTION_POLICY=deploy/distribution.json
ARG RUNTIME_REQUIREMENTS=deploy/requirements-py312.lock
ARG DEBIAN_SNAPSHOT=20261027T000000Z
ENV PIP_DISABLE_PIP_VERSION_CHECK=1 PIP_NO_CACHE_DIR=1 PYTHONDONTWRITEBYTECODE=1
RUN printf 'deb [check-valid-until=no] https://snapshot.debian.org/archive/debian/%s/ bookworm main\ndeb [check-valid-until=no] https://snapshot.debian.org/archive/debian-security/%s/ bookworm-security main\n' "$DEBIAN_SNAPSHOT" "$DEBIAN_SNAPSHOT" > /etc/apt/sources.list \
    && rm /etc/apt/sources.list.d/debian.sources \
    && apt-get update \
    && apt-get install -y --no-install-recommends build-essential libldap2-dev libsasl2-dev libpq-dev libssl-dev libffi-dev \
    && rm -rf /var/lib/apt/lists/*
COPY deploy/build-requirements.lock /locks/build-requirements.lock
COPY ${RUNTIME_REQUIREMENTS} /locks/requirements.lock
RUN python -m pip install --require-hashes -r /locks/build-requirements.lock \
    && python -m venv /venv \
    && /venv/bin/python -m pip install --require-hashes -r /locks/build-requirements.lock \
    && /venv/bin/python -m pip install --no-build-isolation --require-hashes -r /locks/requirements.lock \
    && /venv/bin/python -m pip check
COPY . /source
RUN /venv/bin/python /source/tools/build_distribution.py /source /release --policy "$DISTRIBUTION_POLICY"

FROM ${PYTHON_IMAGE} AS runtime
ARG DEBIAN_SNAPSHOT=20261027T000000Z
ARG SDK_PYTHONPATH=""
ARG RUNTIME_REQUIREMENTS=deploy/requirements-py312.lock
ENV PATH=/venv/bin:$PATH PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 LANG=C.UTF-8 PYTHONPATH=$SDK_PYTHONPATH
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
COPY ${RUNTIME_REQUIREMENTS} /opt/modular/requirements.lock
COPY tests/fixtures/addons /opt/modular/fixtures
RUN if test -d /opt/modular/packages/platform_sdk; then printf 'r1\n' > /opt/modular/startup-profile; else printf 'baseline\n' > /opt/modular/startup-profile; fi
WORKDIR /opt/modular
USER 10001:10001
EXPOSE 8069
ENTRYPOINT ["/venv/bin/python", "/opt/modular/tools/start_worker.py"]
CMD ["-c", "/run/secrets/odoo_config"]
