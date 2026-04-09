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
RUN uv sync --frozen --no-dev

# Copy project files
COPY . /code

RUN chmod +x /code/scripts/entrypoint.sh
RUN sed -i 's/\r$//' /code/scripts/entrypoint.sh

ENTRYPOINT ["/code/scripts/entrypoint.sh"]
