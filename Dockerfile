FROM python:3.11-slim

WORKDIR /app

# Install system deps for yt-dlp and beautifulsoup
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements first for layer caching
COPY requirements.txt .

# Install directly into system Python — no venv needed in Docker
RUN pip install --no-cache-dir -r requirements.txt

# Copy app
COPY . .

ENV PYTHONUNBUFFERED=1
CMD ["python", "agent.py"]