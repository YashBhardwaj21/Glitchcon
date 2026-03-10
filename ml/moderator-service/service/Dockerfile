FROM python:3.11-slim

WORKDIR /app

# Set env vars to avoid writing .pyc files and buffer stdout
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

# Install system dependencies required for FAISS, langdetect
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Install Python requirements
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application source code
COPY ./app /app/app
COPY ./scripts /app/scripts

# Expose default HTTP port
EXPOSE 8001

# Command to run the application (production)
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8001"]
