# Use official Python image
FROM python:3.13-slim

# Create non-root user for better security (optional)
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1
WORKDIR /app

# Install build dependencies (if needed for some packages)
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential gcc \
  && rm -rf /var/lib/apt/lists/*

# Copy and install dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
RUN pip install mysql-connector-python

# Copy application code
COPY . .

# Expose port
EXPOSE 5000

# For production: use gunicorn (multiprocess). Bind to 0.0.0.0
ENV FLASK_ENV=production
CMD ["gunicorn", "--bind", "0.0.0.0:5000", "app:app", "--workers", "3"]
