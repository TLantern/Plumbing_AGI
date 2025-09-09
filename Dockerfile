# Optimized Dockerfile for Whisper v3 Service (CPU-only, smaller size)
FROM python:3.11-slim

# Install system dependencies in one layer
RUN apt-get update && apt-get install -y \
    ffmpeg \
    && rm -rf /var/lib/apt/lists/* \
    && apt-get clean

# Set working directory
WORKDIR /app

# Copy requirements and install Python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir --upgrade pip \
    && pip install --no-cache-dir -r requirements.txt \
    && pip cache purge

# Copy application code
COPY app.py .

# Create directory for Whisper models
RUN mkdir -p /tmp/whisper_models

# Set environment variables for smaller memory footprint
ENV PYTHONUNBUFFERED=1
ENV PYTHONDONTWRITEBYTECODE=1

# Expose port
EXPOSE 8000

# Run the application
CMD ["python", "app.py"]
