#!/usr/bin/env python3
"""Run Celery worker with environment variables loaded."""

import os
import sys
from pathlib import Path
from dotenv import load_dotenv

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

# Load environment variables
env_path = project_root / ".env"
load_dotenv(env_path)

# Verify Redis URL is loaded
redis_url = os.getenv("REDIS_URL")
print(f"Redis URL loaded: {redis_url}")

# Start Celery worker
os.system("celery -A src.tasks.celery_app worker --loglevel=info")