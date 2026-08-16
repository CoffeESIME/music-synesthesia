# syntax=docker/dockerfile:1.7

ARG PYTHON_VERSION=3.11

FROM python:${PYTHON_VERSION}-slim-bookworm AS builder

ENV PIP_DISABLE_PIP_VERSION_CHECK=1 \
    PIP_NO_CACHE_DIR=1 \
    PYTHONDONTWRITEBYTECODE=1

WORKDIR /build

RUN apt-get update \
    && apt-get install --yes --no-install-recommends \
        build-essential \
        libsndfile1-dev \
        portaudio19-dev \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt ./

RUN python -m venv /opt/venv \
    && /opt/venv/bin/python -m pip install --upgrade "pip<25" "setuptools<70" wheel \
    && /opt/venv/bin/python -m pip install numpy==1.26.4 \
    && /opt/venv/bin/python -m pip install --no-build-isolation -r requirements.txt


FROM python:${PYTHON_VERSION}-slim-bookworm AS runtime

ENV APP_PORT=8765 \
    PATH="/opt/venv/bin:${PATH}" \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

RUN apt-get update \
    && apt-get install --yes --no-install-recommends \
        libportaudio2 \
        libsndfile1 \
    && rm -rf /var/lib/apt/lists/* \
    && groupadd --gid 10001 sinestesia \
    && useradd --uid 10001 --gid sinestesia --groups audio --create-home --shell /usr/sbin/nologin sinestesia

WORKDIR /app

COPY --from=builder /opt/venv /opt/venv
COPY --chown=sinestesia:sinestesia api ./api
COPY --chown=sinestesia:sinestesia audio ./audio
COPY --chown=sinestesia:sinestesia core ./core
COPY --chown=sinestesia:sinestesia engine ./engine
COPY --chown=sinestesia:sinestesia hardware ./hardware
COPY --chown=sinestesia:sinestesia static ./static

USER sinestesia

EXPOSE 8765

HEALTHCHECK --interval=15s --timeout=3s --start-period=20s --retries=3 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8765/api/status', timeout=2)" || exit 1

CMD ["sh", "-c", "exec uvicorn api.main:app --host 0.0.0.0 --port ${APP_PORT} --workers 1"]
