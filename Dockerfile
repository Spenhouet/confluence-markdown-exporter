# syntax=docker/dockerfile:1.7

# ---- builder ---------------------------------------------------------------
FROM python:3.12-slim AS builder

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    PIP_NO_CACHE_DIR=1 \
    UV_LINK_MODE=copy \
    UV_PYTHON_DOWNLOADS=never

RUN apt-get update \
    && apt-get install -y --no-install-recommends build-essential \
    && rm -rf /var/lib/apt/lists/*

COPY --from=ghcr.io/astral-sh/uv:0.8 /uv /usr/local/bin/uv

WORKDIR /build

COPY pyproject.toml uv.lock README.md ./
COPY confluence_markdown_exporter ./confluence_markdown_exporter

RUN uv build --no-sources

# ---- runtime ---------------------------------------------------------------
FROM python:3.12-slim AS runtime

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    PIP_NO_CACHE_DIR=1 \
    HOME=/data/config \
    XDG_CONFIG_HOME=/data/config \
    CME_CONFIG_PATH=/data/config/app_data.json \
    CME_EXPORT__OUTPUT_PATH=/data/output

RUN groupadd --system --gid 1000 cme \
    && useradd  --system --uid 1000 --gid cme --home-dir /data/config --shell /usr/sbin/nologin cme \
    && mkdir -p /data/output /data/config \
    && chown -R cme:cme /data

COPY --from=builder /build/dist/*.whl /tmp/

RUN pip install --no-cache-dir /tmp/*.whl \
    && rm /tmp/*.whl

USER cme
WORKDIR /data/output

ENTRYPOINT ["confluence-markdown-exporter"]
CMD ["--help"]
