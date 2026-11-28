# python 3.15.2-alpine3.24 multi-arch index (amd64 and arm64 release builds)
FROM python:3.15.2-alpine3.24@sha256:0f9552bb28711333da16915ec146f5e6bb44a7fdac9ced15dc17c2e0206346dd

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
