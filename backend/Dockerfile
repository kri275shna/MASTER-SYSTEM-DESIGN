FROM python:3.12-slim

# Set environment variables
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

WORKDIR /backend

# Install system dependencies for OpenCV and postgresql
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    libpq-dev \
    glib-2.0 \
    && rm -rf /var/lib/apt/lists/*

# Install python dependencies
COPY requirements.txt /backend/
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY . /backend/

EXPOSE 8000

# Run FastAPI using uvicorn
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
