FROM apache/spark:3.5.0

USER root

# Install psycopg2 binary (no gcc issues)
RUN pip install --no-cache-dir pandas psycopg2-binary

USER spark
