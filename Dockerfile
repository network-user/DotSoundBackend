FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    POETRY_VERSION=1.8.3 \
    POETRY_HOME="/opt/poetry" \
    POETRY_VIRTUALENVS_CREATE=false \
    PATH="/opt/poetry/bin:$PATH"

RUN apt-get update && apt-get install -y --no-install-recommends \
    ffmpeg \
    libpq-dev \
    gcc \
    curl \
    libmagic1 \
    && rm -rf /var/lib/apt/lists/*

RUN curl -sSL https://install.python-poetry.org | python3 -

WORKDIR /app

COPY DotSoundPrivateCore /DotSoundPrivateCore

COPY DotSoundBackend/pyproject.toml DotSoundBackend/poetry.lock ./
RUN poetry lock --no-update && poetry install --no-interaction --no-ansi --no-root

# PrivateCore runtime extras are installed separately so they never appear
# in the backend's declarative dependency graph.
RUN pip install --no-cache-dir "/DotSoundPrivateCore[ml]"

COPY DotSoundBackend/. .
RUN poetry install --no-interaction --no-ansi

ENV UVICORN_HOST=0.0.0.0 \
    UVICORN_PORT=8000

EXPOSE 8000

CMD ["sh", "-c", "uvicorn app.main:app --host \"$UVICORN_HOST\" --port \"$UVICORN_PORT\""]
