FROM python:3.10-slim-bullseye

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

ENTRYPOINT ["uv", "run", "python3", "src/mock_chiv2_host/mock_host.py"]
