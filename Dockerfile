# python 3.14.6-alpine3.24 (tag used for multi-arch release builds)
FROM python:3.14.6-alpine3.24

RUN apk add --no-cache \
    build-base \
    libffi-dev \
    openssl-dev

RUN pip install poetry

WORKDIR /action

COPY pyproject.toml poetry.lock ./

RUN poetry config virtualenvs.create true
RUN poetry config virtualenvs.in-project true

COPY . .

RUN poetry install --no-root --without dev

ENV PYTHONPATH=/action/src
COPY entrypoint.sh /entrypoint.sh
RUN chmod +x /entrypoint.sh
ENTRYPOINT ["/entrypoint.sh"]
