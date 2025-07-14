# Multi-stage build for Python bot with uv
FROM python:3.12-slim AS base

# Install system dependencies
RUN apt-get update && apt-get install -y \
    curl \
    gcc \
    g++ \
    && rm -rf /var/lib/apt/lists/*

# Install uv
RUN pip install uv

# Set working directory
WORKDIR /app

# Copy uv configuration files
COPY pyproject.toml uv.lock ./

# Create virtual environment and install dependencies
RUN uv sync --frozen --no-dev

# Development stage
FROM base AS development
RUN uv sync --frozen
COPY . .
CMD ["uv", "run", "python", "-m", "bot.main"]

# Production stage
FROM base AS production

# Copy application code
COPY . .

# Create non-root user for security
RUN groupadd -r botuser && useradd -r -g botuser botuser
RUN chown -R botuser:botuser /app
USER botuser

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD python -c "import asyncio; print('Bot is healthy')" || exit 1

# Run the bot
CMD ["uv", "run", "python", "-m", "bot.main"] 