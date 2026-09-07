FROM ghcr.io/astral-sh/uv:python3.12-bookworm-slim

WORKDIR /app

ENV UV_COMPILE_BYTECODE=1
ENV UV_LINK_MODE=copy
ENV PYTHONUNBUFFERED=1

COPY pyproject.toml uv.lock README.md ./
COPY src ./src
COPY data ./data

RUN uv sync --locked --no-dev

# Railway's API service overrides this with its Uvicorn command.
# The default is the long-running LiveKit voice worker.
CMD ["uv", "run", "--no-sync", "saarthi-agent", "start"]
