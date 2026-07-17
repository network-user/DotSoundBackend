# NOTE: pin the base image by digest before production deploy, e.g.
#   FROM python:3.12-slim@sha256:<digest>
# (resolve with `docker buildx imagetools inspect python:3.12-slim`).
# Left as a floating tag here so offline checkouts still build.
FROM python:3.12-slim

# MALLOC_ARENA_MAX=2 caps glibc per-thread malloc arenas; long-running
# Python processes with thread pools (yt-dlp scans, to_thread) otherwise
# grow one arena per thread and fragment RSS by tens of MB.
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    MALLOC_ARENA_MAX=2 \
    POETRY_VERSION=1.8.3 \
    POETRY_VIRTUALENVS_CREATE=false \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    PIP_NO_CACHE_DIR=1

# Static ffmpeg/ffprobe (~100MB binaries) instead of `apt install ffmpeg`,
# which pulls ~250 multimedia/X11 packages (~700MB) and fails on the
# small prod box with:
#   E: You don't have enough free space in /var/cache/apt/archives/
COPY --from=mwader/static-ffmpeg:7.1.1 /ffmpeg /usr/local/bin/ffmpeg
COPY --from=mwader/static-ffmpeg:7.1.1 /ffprobe /usr/local/bin/ffprobe

# policy-rc.d exit 101 tells invoke-rc.d to skip service start/stop
# during apt-get install, preventing the system tor daemon from
# starting on port 9050 and conflicting with the stem-managed pool.
RUN printf '#!/bin/sh\nexit 101\n' > /usr/sbin/policy-rc.d \
    && chmod +x /usr/sbin/policy-rc.d

# Runtime OS deps only. No gcc/libpq-dev: asyncpg, cryptography, Pillow
# ship manylinux wheels for CPython 3.12 and do not need a compiler.
RUN apt-get update && apt-get install -y --no-install-recommends \
    ca-certificates \
    curl \
    libmagic1 \
    tor \
    && rm -rf /var/lib/apt/lists/* /var/cache/apt/archives/*

# Remove install-time policy guard; clean the system tor data dir so
# no stale lock/cookie files are left behind. The stem pool writes its
# own DataDirectory via tempfile.mkdtemp() at runtime.
RUN rm -f /usr/sbin/policy-rc.d \
    && rm -rf /var/lib/tor \
    && if [ -f /etc/init.d/tor ]; then update-rc.d -f tor remove || true; fi

# Poetry in an isolated venv; only the `poetry` binary is linked onto
# PATH so system python3/pip stay the install targets for project deps
# (POETRY_VIRTUALENVS_CREATE=false -> system site-packages).
RUN python3 -m venv /opt/poetry \
    && /opt/poetry/bin/pip install --no-cache-dir \
        "poetry==${POETRY_VERSION}" \
    && ln -sf /opt/poetry/bin/poetry /usr/local/bin/poetry

WORKDIR /app

# PrivateCore is a path-dependency declared in pyproject.toml
# (dotsound-private-core = { path = "../DotSoundPrivateCore", ... }), so it must
# exist BEFORE `poetry install` can resolve it. Copy it first, then install.
# Trade-off: the dependency layer no longer stays cached across PrivateCore-only
# changes (poetry re-runs when PrivateCore is pulled fresh). The alternative -
# keeping PrivateCore out of poetry's graph and installing it only via pip below
# - would restore that caching but needs the path-dep removed from pyproject and
# a regenerated lock.
COPY DotSoundPrivateCore /DotSoundPrivateCore

# Defense-in-depth: the private core's local secret files must never persist in
# an image layer. Dockerfile.dockerignore already excludes them under BuildKit;
# this also covers legacy builds. Done before install so they never enter it.
RUN rm -f /DotSoundPrivateCore/.env /DotSoundPrivateCore/.env.*

# The lockfile is committed and kept in sync with pyproject, so install straight
# from it rather than regenerating on build.
COPY DotSoundBackend/pyproject.toml DotSoundBackend/poetry.lock ./
RUN poetry install --no-interaction --no-ansi --no-root

# PrivateCore runtime extras are installed separately so they never appear
# in the backend's declarative dependency graph.
RUN pip install --no-cache-dir \
    "/DotSoundPrivateCore[outbound,scanners,proxies]"

COPY DotSoundBackend/. .
RUN poetry install --no-interaction --no-ansi

# Drop root. uvicorn, ffmpeg and the stem-managed tor pool all run fine
# unprivileged (tor uses a tempdir DataDirectory at runtime, and
# PYTHONDONTWRITEBYTECODE=1 means no .pyc writes into /app). The prod
# overlay runs the image code directly (no source bind-mount, DEBUG off),
# so /app is owned by appuser.
# NOTE for dev: the base compose bind-mounts the host repo over /app - if
# you enable debug file logging there, make the host ./logs dir writable
# by uid 10001 (or run the dev container as root).
RUN useradd --create-home --uid 10001 appuser \
    && chown -R appuser:appuser /app
USER appuser

ENV UVICORN_HOST=0.0.0.0 \
    UVICORN_PORT=8000

EXPOSE 8000

CMD ["sh", "-c", "uvicorn app.main:app --host \"$UVICORN_HOST\" --port \"$UVICORN_PORT\" --no-access-log"]
