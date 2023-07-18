FROM python:3.10-slim-bullseye

ARG ENV

ENV ENV=${ENV} \
  PYTHONFAULTHANDLER=1 \
  PYTHONUNBUFFERED=1 \
  PYTHONHASHSEED=random \
  PIP_NO_CACHE_DIR=off \
  PIP_DISABLE_PIP_VERSION_CHECK=on \
  PIP_DEFAULT_TIMEOUT=100 \
  POETRY_VERSION=1.5.1

RUN apt-get update
RUN apt-get install python3-pip python3 curl -y
RUN pip3 install poetry

WORKDIR /code
COPY poetry.lock pyproject.toml /code/

# Creating folders, and files for a project:
COPY . /code

RUN poetry config virtualenvs.create false \
  && poetry install --no-dev --no-interaction --no-ansi

ENTRYPOINT ["poetry", "run", "gunicorn", "server_browser_backend:app"]
