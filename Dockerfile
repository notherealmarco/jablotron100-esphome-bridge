FROM ghcr.io/astral-sh/uv:alpine

WORKDIR /app

ENV UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy

COPY pyproject.toml uv.lock README.md ./
RUN uv sync --frozen --no-dev --no-install-project

COPY src ./src
RUN uv sync --frozen --no-dev

EXPOSE 6053/udp 6053/tcp

VOLUME ["/app/data"]

ENTRYPOINT ["/app/.venv/bin/jablo2esphome"]
CMD ["/app/config.yaml"]
