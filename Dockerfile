FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    POETRY_VERSION=1.8.3 \
    POETRY_HOME="/opt/poetry" \
    POETRY_VIRTUALENVS_CREATE=false \
    PATH="/opt/poetry/bin:$PATH"

# policy-rc.d exit 101 tells invoke-rc.d to skip service start/stop
# during apt-get install, preventing the system tor daemon from
# starting on port 9050 and conflicting with the stem-managed pool.
RUN printf '#!/bin/sh\nexit 101\n' > /usr/sbin/policy-rc.d \
    && chmod +x /usr/sbin/policy-rc.d

RUN apt-get update && apt-get install -y --no-install-recommends \
    ffmpeg \
    libpq-dev \
    gcc \
    curl \
    libmagic1 \
    tor \
    && rm -rf /var/lib/apt/lists/*

# Remove install-time policy guard; clean the system tor data dir so
# no stale lock/cookie files are left behind. The stem pool writes its
# own DataDirectory via tempfile.mkdtemp() at runtime.
RUN rm -f /usr/sbin/policy-rc.d \
    && rm -rf /var/lib/tor \
    && if [ -f /etc/init.d/tor ]; then update-rc.d -f tor remove || true; fi

RUN curl -sSL https://install.python-poetry.org | python3 -

WORKDIR /app

COPY DotSoundPrivateCore /DotSoundPrivateCore

COPY DotSoundBackend/pyproject.toml DotSoundBackend/poetry.lock ./
RUN poetry lock --no-update && poetry install --no-interaction --no-ansi --no-root

# PrivateCore runtime extras are installed separately so they never appear
# in the backend's declarative dependency graph.
RUN pip install --no-cache-dir \
    "/DotSoundPrivateCore[outbound,scanners,proxies]"

COPY DotSoundBackend/. .
RUN poetry install --no-interaction --no-ansi

ENV UVICORN_HOST=0.0.0.0 \
    UVICORN_PORT=8000

EXPOSE 8000

CMD ["sh", "-c", "uvicorn app.main:app --host \"$UVICORN_HOST\" --port \"$UVICORN_PORT\" --no-access-log"]
