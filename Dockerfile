# The builder image, used to build the virtual environment
FROM python:3.13-bookworm as builder

RUN pip install poetry==2.1.3

ENV POETRY_NO_INTERACTION=1 \
    POETRY_VIRTUALENVS_IN_PROJECT=1 \
    POETRY_VIRTUALENVS_CREATE=1 \
    POETRY_CACHE_DIR=/tmp/poetry_cache

WORKDIR /app

COPY pyproject.toml poetry.lock ./
RUN touch README.md

RUN poetry install --without dev --no-root && rm -rf $POETRY_CACHE_DIR

# The runtime image, used to just run the code provided its virtual environment
FROM python:3.13-slim-bookworm as runtime

ENV VIRTUAL_ENV=/app/.venv \
    PATH="/app/.venv/bin:$PATH" \
    PYTHONPATH="$PYTHONPATH:/ascifight"

COPY --from=builder ${VIRTUAL_ENV} ${VIRTUAL_ENV}

COPY ascifight ./ascifight

EXPOSE 8000

ENTRYPOINT ["python", "-m", "main"]
