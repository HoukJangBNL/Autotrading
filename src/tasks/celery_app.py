"""Celery application configuration."""

from celery import Celery
from kombu import Queue, Exchange
from datetime import timedelta
import os

# 설정 가져오기
redis_url = os.getenv("REDIS_URL", "redis://localhost:6379/0")

# Celery 애플리케이션 인스턴스 생성
celery_app = Celery(
    "autotrading",
    broker=redis_url,
    backend=redis_url,
    include=[
        "src.tasks.data_mining",
        "src.tasks.backtesting",
    ]
)

# Celery 설정
celery_app.conf.update(
    # Task 설정
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    result_expires=3600,  # 1시간 후 결과 만료
    timezone="America/New_York",  # 뉴욕 시간대 (주식시장)
    enable_utc=True,
    
    # Worker 설정
    worker_prefetch_multiplier=4,
    worker_max_tasks_per_child=1000,
    
    # 재시도 설정
    task_acks_late=True,
    task_reject_on_worker_lost=True,
    
    # 라우팅 설정
    task_routes={
        "src.tasks.data_mining.*": {"queue": "data_mining"},
        "src.tasks.backtesting.*": {"queue": "backtesting"},
    },
    
    # Queue 정의
    task_queues=(
        Queue("default", Exchange("default"), routing_key="default"),
        Queue("data_mining", Exchange("data_mining"), routing_key="data_mining", priority=5),
        Queue("backtesting", Exchange("backtesting"), routing_key="backtesting", priority=3),
    ),
    
    # Beat 스케줄 (정기 작업)
    beat_schedule={
        # 매일 오전 5시에 데이터 갭 체크
        "check-data-gaps": {
            "task": "src.tasks.data_mining.check_and_fill_gaps",
            "schedule": timedelta(hours=24),
            "options": {"queue": "data_mining"},
        },
        # 매주 일요일 오전 6시에 백테스팅 실행
        "weekly-backtesting": {
            "task": "src.tasks.backtesting.run_weekly_backtests",
            "schedule": timedelta(weeks=1),
            "options": {"queue": "backtesting"},
        },
    },
)

# 태스크 관련 설정
celery_app.conf.task_annotations = {
    "*": {"rate_limit": "100/m"},  # 기본 rate limit
    "src.tasks.data_mining.mine_ticker_data": {"rate_limit": "60/m"},  # Schwab API 제한 고려
}

# Celery 시그널 핸들러
@celery_app.task(bind=True)
def debug_task(self):
    """디버깅용 테스트 태스크."""
    print(f"Request: {self.request!r}")
    return "pong"