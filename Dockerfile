FROM python:3.12-slim-bookworm AS builder

COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /bin/
WORKDIR /build

# uv needs every workspace manifest, but client/tooling sources are not build inputs.
COPY pyproject.toml uv.lock /build/
COPY packages/server-browser-models/pyproject.toml /build/packages/server-browser-models/pyproject.toml
COPY packages/server-browser-server/pyproject.toml /build/packages/server-browser-server/pyproject.toml
COPY packages/server-browser-fastapi/pyproject.toml /build/packages/server-browser-fastapi/pyproject.toml
COPY packages/server-browser-client/pyproject.toml /build/packages/server-browser-client/pyproject.toml
COPY packages/server-browser-codegen/pyproject.toml /build/packages/server-browser-codegen/pyproject.toml
RUN uv export --frozen --no-dev --no-emit-workspace --no-hashes --output-file /requirements.txt
RUN uv venv /opt/venv
RUN uv pip sync --python /opt/venv/bin/python /requirements.txt

# Build only the backend and its three runtime SDK dependencies.
COPY README.md /build/
COPY assets /build/assets
COPY src/server_browser_backend /build/src/server_browser_backend
COPY packages/server-browser-models/hatch_build.py /build/packages/server-browser-models/hatch_build.py
COPY packages/server-browser-models/src /build/packages/server-browser-models/src
COPY packages/server-browser-server/src /build/packages/server-browser-server/src
COPY packages/server-browser-fastapi/src /build/packages/server-browser-fastapi/src
RUN uv build --wheel --package server-browser-models --out-dir /wheels
RUN uv build --wheel --package server-browser-server --out-dir /wheels
RUN uv build --wheel --package server-browser-fastapi --out-dir /wheels
RUN uv build --wheel --package chivalry2-unofficial-server-browser-backend --out-dir /wheels
RUN uv pip install --python /opt/venv/bin/python --no-deps /wheels/*.whl
RUN uv pip check --python /opt/venv/bin/python

FROM python:3.12-slim-bookworm AS runtime

ARG ENV
ENV ENV=${ENV} \
  PYTHONFAULTHANDLER=1 \
  PYTHONUNBUFFERED=1 \
  PYTHONHASHSEED=random \
  PATH="/opt/venv/bin:${PATH}"

WORKDIR /code
COPY --from=builder /opt/venv /opt/venv
COPY config /code/config
COPY --chmod=755 scripts/entrypoint.sh /usr/local/bin/server-browser-entrypoint
RUN sed -i 's/\r$//' /usr/local/bin/server-browser-entrypoint

ENTRYPOINT ["/usr/local/bin/server-browser-entrypoint"]
