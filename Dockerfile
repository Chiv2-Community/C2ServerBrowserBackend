FROM python:3.12-slim-bookworm

ARG ENV

ENV ENV=${ENV} \
  PYTHONFAULTHANDLER=1 \
  PYTHONUNBUFFERED=1 \
  PYTHONHASHSEED=random

# Install uv
COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /bin/

WORKDIR /code

# Install dependencies
COPY pyproject.toml uv.lock /code/
COPY packages/server-browser-models/pyproject.toml /code/packages/server-browser-models/pyproject.toml
COPY packages/server-browser-server/pyproject.toml /code/packages/server-browser-server/pyproject.toml
COPY packages/server-browser-fastapi/pyproject.toml /code/packages/server-browser-fastapi/pyproject.toml
COPY packages/server-browser-client/pyproject.toml /code/packages/server-browser-client/pyproject.toml
RUN uv sync --frozen --no-dev --no-install-workspace

# Copy project files
COPY . /code
RUN uv sync --frozen --no-dev

RUN chmod +x /code/scripts/entrypoint.sh
RUN sed -i 's/\r$//' /code/scripts/entrypoint.sh

ENTRYPOINT ["/code/scripts/entrypoint.sh"]
