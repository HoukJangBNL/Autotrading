# Celery Guide: Background Jobs

This project uses two Celery applications for separate concerns:

- src/services/celery_app.py ("service" workers)
  - Queues: periodic app health, strategy checks, portfolio updates
  - Command: celery -A src.services.celery_app worker -l info
  - Beat:    celery -A src.services.celery_app beat -l info

- src/tasks/celery_app.py ("data" workers)
  - Queues: data_mining, backtesting (see task_routes/task_queues)
  - Command: celery -A src.tasks.celery_app worker -l info -Q data_mining,backtesting

## Environment
- Redis (broker/backend): REDIS_* from Settings or redis://localhost:6379/0
- Database: PostgreSQL/Timescale per docker-compose.yml

## Development commands
```bash
# Start Redis & Postgres via docker-compose
docker-compose up -d postgres redis

# Service worker + beat
celery -A src.services.celery_app worker -l info
celery -A src.services.celery_app beat -l info

# Data workers
celery -A src.tasks.celery_app worker -l info -Q data_mining
celery -A src.tasks.celery_app worker -l info -Q backtesting
```

## Notes
- Use queues to isolate workloads.
- Long-running or batch operations should run in data_* queues.
- Avoid network or DB heavy operations in FastAPI request lifecycle; dispatch a task.

