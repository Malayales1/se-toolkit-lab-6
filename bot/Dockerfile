# Dockerfile for the System Agent (bot)
# Adapted from the main Dockerfile and https://github.com/astral-sh/uv-docker-example

# Stage 1: Build the application
FROM harbor.pg.innopolis.university/docker-hub-cache/astral/uv:python3.14-bookworm-slim AS builder

ENV UV_COMPILE_BYTECODE=1 UV_LINK_MODE=copy

# Omit development dependencies
ENV UV_NO_DEV=1

# Disable Python downloads, use system interpreter
ENV UV_PYTHON_DOWNLOADS=0

WORKDIR /app

# Install dependencies
RUN --mount=type=cache,target=/root/.cache/uv \
    --mount=type=bind,source=uv.lock,target=uv.lock \
    --mount=type=bind,source=pyproject.toml,target=pyproject.toml \
    uv sync --locked --no-install-project

# Copy agent.py
COPY agent.py /app/agent.py

# Stage 2: Final runtime image
FROM harbor.pg.innopolis.university/docker-hub-cache/python:3.14.2-slim-bookworm

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1
ENV LANG=C.UTF-8

# Setup non-root user
RUN groupadd --system --gid 999 nonroot \
    && useradd --system --gid 999 --uid 999 --create-home nonroot

# Copy application from builder
COPY --from=builder --chown=nonroot:nonroot /app /app

# Add virtual environment to PATH
ENV PATH="/app/.venv/bin:$PATH"

# Use non-root user
USER nonroot

WORKDIR /app

# Run the agent CLI
# The agent is a CLI tool, so we use python agent.py directly
# Arguments are passed via docker-compose command override
CMD ["python", "agent.py"]
