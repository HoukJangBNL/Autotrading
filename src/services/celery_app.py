"""
Celery application configuration for background tasks.
"""
from celery import Celery
from src.config import settings

# Create Celery app
celery_app = Celery(
    'autotrading',
    broker=f'redis://:{settings.redis.password if settings.redis.password else ""}@{settings.redis.host}:{settings.redis.port}/0',
    backend=f'redis://:{settings.redis.password if settings.redis.password else ""}@{settings.redis.host}:{settings.redis.port}/1',
    include=[
        'src.services.tasks',
    ]
)

# Configure Celery
celery_app.conf.update(
    task_serializer='json',
    accept_content=['json'],
    result_serializer='json',
    timezone='UTC',
    enable_utc=True,
    broker_connection_retry_on_startup=True,
    beat_schedule={
        'update-market-data': {
            'task': 'src.services.tasks.update_market_data',
            'schedule': 60.0,  # Every minute
        },
        'check-strategy-signals': {
            'task': 'src.services.tasks.check_strategy_signals',
            'schedule': 30.0,  # Every 30 seconds
        },
        'update-portfolio': {
            'task': 'src.services.tasks.update_portfolio',
            'schedule': 300.0,  # Every 5 minutes
        },
    },
)