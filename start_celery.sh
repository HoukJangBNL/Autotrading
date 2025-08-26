#!/bin/bash
# Start Celery worker with environment variables

# Load environment variables
export $(grep -v '^#' .env | xargs)

# Verify Redis URL
echo "Redis URL: $REDIS_URL"

# Start Celery worker
celery -A src.tasks.celery_app worker --loglevel=info