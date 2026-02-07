FROM python:3.11-slim

WORKDIR /app

COPY binforge/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY binforge/src ./src
COPY binforge/tests ./tests
COPY pytest.ini .

# Python can import from src
ENV PYTHONPATH=/app/src

# Default command runs pytest
CMD ["pytest", "tests/"]
