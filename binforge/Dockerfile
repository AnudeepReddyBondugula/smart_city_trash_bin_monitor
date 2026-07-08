FROM python:3.12-slim

WORKDIR /app

# Install system dependencies if needed (e.g. for asyncpg)
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    && rm -rf /var/lib/apt/lists/*

# Install Python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application source code
COPY . .

# Set python path so module imports work
ENV PYTHONPATH=/app

# Command to run the simulator
CMD ["python", "src/main.py"]
