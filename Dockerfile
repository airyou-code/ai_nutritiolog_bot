FROM --platform=linux/amd64 python:3.12-slim

ENV PYTHONUNBUFFERED 1
ENV PYTHONDONTWRITEBYTECODE 1

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

# Create virtual environment and install production dependencies
RUN uv sync --frozen --no-dev

# Copy application code
COPY . .

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD python -c "import sys; sys.exit(0)" || exit 1

# Run the bot asynchronously in production
CMD ["uv", "run", "python", "-m", "bot.main"] 