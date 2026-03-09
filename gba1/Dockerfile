FROM python:3.11-slim

WORKDIR /app

# Install system deps
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Copy SDK first (local dependency)
COPY ../moderator-service/sdk /sdk

# Copy requirements and install
COPY requirements.txt .
RUN pip install --no-cache-dir -e /sdk && \
    pip install --no-cache-dir -r requirements.txt

# Copy app source
COPY . .

EXPOSE 8002

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8002"]
