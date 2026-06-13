FROM python:3.13-slim

# Install OS dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    gcc \
    git \
    libpq-dev \
    && rm -rf /var/lib/apt/lists/*

# Install uv
RUN pip install --no-cache-dir uv

# App directory
WORKDIR /var/TechSupportBot

# Copy dependency files first for Docker layer caching
COPY pyproject.toml uv.lock ./

# Install dependencies into project venv
RUN uv sync --frozen --no-dev

# Copy project files
COPY . .

# Move into bot directory
WORKDIR /var/TechSupportBot

# Run bot
CMD ["uv", "run", "--", "python3", "-u", "main.py"]
