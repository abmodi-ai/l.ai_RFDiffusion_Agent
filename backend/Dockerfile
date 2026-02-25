FROM python:3.11-slim

WORKDIR /app

# System dependencies for psycopg2 and bcrypt
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    libpq-dev \
    && rm -rf /var/lib/apt/lists/*

# Install Python dependencies
COPY backend/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy backend code
COPY backend/app/ app/

# Create data directories
RUN mkdir -p /data/uploads /data/outputs

ENV UPLOAD_DIR=/data/uploads
ENV OUTPUT_DIR=/data/outputs

EXPOSE 8000

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
