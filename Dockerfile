# syntax=docker/dockerfile:1.7

# ---- builder ---------------------------------------------------------------
FROM python:3.12-slim AS builder

ARG TARGETARCH

COPY --from=ghcr.io/astral-sh/uv:0.8 /uv /uvx /usr/local/bin/

ENV UV_LINK_MODE=copy \
    UV_COMPILE_BYTECODE=1 \
    UV_PYTHON_DOWNLOADS=never

WORKDIR /app

# Install runtime dependencies only. This layer is cached unless uv.lock or
# pyproject.toml change. Metadata is bind-mounted so it does not get baked
# into the layer and invalidate it on unrelated edits.
RUN --mount=type=cache,target=/root/.cache/uv,id=uv-$TARGETARCH \
    --mount=type=bind,source=uv.lock,target=uv.lock \
    --mount=type=bind,source=pyproject.toml,target=pyproject.toml \
    --mount=type=bind,source=README.md,target=README.md \
    uv sync --locked --no-install-project --no-editable --no-dev

# Install the project itself into the venv. Invalidates on source edits.
COPY pyproject.toml uv.lock README.md ./
COPY confluence_markdown_exporter ./confluence_markdown_exporter
RUN --mount=type=cache,target=/root/.cache/uv,id=uv-$TARGETARCH \
    uv sync --locked --no-editable --no-dev

# ---- runtime ---------------------------------------------------------------
FROM python:3.12-slim AS runtime

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PATH="/app/.venv/bin:$PATH" \
    HOME=/data/config \
    XDG_CONFIG_HOME=/data/config \
    CME_CONFIG_PATH=/data/config/app_data.json \
    CME_EXPORT__OUTPUT_PATH=/data/output

RUN groupadd --system --gid 1000 cme \
    && useradd  --system --uid 1000 --gid cme --home-dir /data/config --shell /usr/sbin/nologin cme \
    && mkdir -p /data/output /data/config \
    && chown -R cme:cme /data

# Copy only the venv, not the source. `--no-editable` made the install
# self-contained so the source tree is not needed at runtime.
COPY --from=builder /app/.venv /app/.venv

USER cme
WORKDIR /data/output

ENTRYPOINT ["confluence-markdown-exporter"]
CMD ["--help"]
