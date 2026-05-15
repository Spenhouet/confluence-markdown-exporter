# syntax=docker/dockerfile:1.7

# ---- builder ---------------------------------------------------------------
FROM python:3.12-slim AS builder

ARG TARGETARCH

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    UV_LINK_MODE=copy \
    UV_PYTHON_DOWNLOADS=never

# Keep apt archives in BuildKit caches so repeated builds skip the download.
RUN --mount=type=cache,target=/var/cache/apt,sharing=locked,id=apt-cache-$TARGETARCH \
    --mount=type=cache,target=/var/lib/apt,sharing=locked,id=apt-lib-$TARGETARCH \
    rm -f /etc/apt/apt.conf.d/docker-clean \
    && apt-get update \
    && apt-get install -y --no-install-recommends build-essential

COPY --from=ghcr.io/astral-sh/uv:0.8 /uv /usr/local/bin/uv

WORKDIR /build

# Resolve deps from the lockfile and emit requirements.txt for the runtime
# stage. This layer is cached unless uv.lock / pyproject.toml change, which
# decouples dependency installation from source-code edits.
COPY pyproject.toml uv.lock README.md ./
RUN --mount=type=cache,target=/root/.cache/uv,id=uv-$TARGETARCH \
    uv export --frozen --no-emit-project --no-dev --format requirements.txt \
        -o /build/requirements.txt

# Build the project wheel. Only this layer needs to invalidate on source edits.
COPY confluence_markdown_exporter ./confluence_markdown_exporter
RUN --mount=type=cache,target=/root/.cache/uv,id=uv-$TARGETARCH \
    uv build --no-sources

# ---- runtime ---------------------------------------------------------------
FROM python:3.12-slim AS runtime

ARG TARGETARCH

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    HOME=/data/config \
    XDG_CONFIG_HOME=/data/config \
    CME_CONFIG_PATH=/data/config/app_data.json \
    CME_EXPORT__OUTPUT_PATH=/data/output

RUN groupadd --system --gid 1000 cme \
    && useradd  --system --uid 1000 --gid cme --home-dir /data/config --shell /usr/sbin/nologin cme \
    && mkdir -p /data/output /data/config \
    && chown -R cme:cme /data

# Install runtime dependencies in a dedicated layer. This layer only
# invalidates when the resolved requirements.txt changes (i.e. uv.lock /
# pyproject.toml updates), not on every source edit.
COPY --from=builder /build/requirements.txt /tmp/requirements.txt
RUN --mount=type=cache,target=/root/.cache/pip,id=pip-$TARGETARCH \
    pip install -r /tmp/requirements.txt \
    && rm /tmp/requirements.txt

# Install the project wheel without re-resolving deps. Fast, source-bound.
COPY --from=builder /build/dist/*.whl /tmp/
RUN --mount=type=cache,target=/root/.cache/pip,id=pip-$TARGETARCH \
    pip install --no-deps /tmp/*.whl \
    && rm /tmp/*.whl

USER cme
WORKDIR /data/output

ENTRYPOINT ["confluence-markdown-exporter"]
CMD ["--help"]
