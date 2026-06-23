# python 3.14.6-alpine3.24
FROM python@sha256:26730869004e2b9c4b9ad09cab8625e81d256d1ce97e72df5520e806b1709f92

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
