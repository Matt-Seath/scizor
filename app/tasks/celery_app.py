from celery import Celery
from celery.schedules import crontab
from app.config.settings import settings
import structlog

logger = structlog.get_logger(__name__)

# Create Celery app
celery_app = Celery(
    "trading_system",
    broker=settings.celery_broker_url,
    backend=settings.celery_result_backend,
    include=["app.tasks.data_collection", "app.tasks.monitoring"]
)

# Configure Celery
celery_app.conf.update(
    task_serializer='json',
    accept_content=['json'],
    result_serializer='json',
    timezone='Australia/Sydney',
    enable_utc=True,
    
    # Task routing
    task_routes={
        'app.tasks.data_collection.*': {'queue': 'data_collection'},
        'app.tasks.monitoring.*': {'queue': 'monitoring'},
    },
    
    # Worker configuration
    worker_prefetch_multiplier=1,
    task_acks_late=True,
    worker_max_tasks_per_child=1000,
    
    # Retry configuration
    task_annotations={
        '*': {'rate_limit': '10/s'},
        'app.tasks.data_collection.collect_daily_asx_data': {
            'rate_limit': '1/m',
            'max_retries': 3,
            'default_retry_delay': 300  # 5 minutes
        }
    }
)

# Beat schedule for periodic tasks
celery_app.conf.beat_schedule = {
    'collect-daily-asx-data': {
        'task': 'app.tasks.data_collection.collect_daily_asx_data',
        'schedule': crontab(hour=16, minute=10, day_of_week='1-5'),  # 4:10 PM weekdays
        'options': {'queue': 'data_collection'}
    },
    'validate-data-quality': {
        'task': 'app.tasks.data_collection.validate_daily_data',
        'schedule': crontab(hour=16, minute=30, day_of_week='1-5'),  # 4:30 PM weekdays
        'options': {'queue': 'data_collection'}
    },
    'monitor-system-health': {
        'task': 'app.tasks.monitoring.check_system_health',
        'schedule': crontab(minute='*/5'),  # Every 5 minutes
        'options': {'queue': 'monitoring'}
    },
    'weekly-performance-report': {
        'task': 'app.tasks.monitoring.generate_weekly_report',
        'schedule': crontab(hour=18, minute=0, day_of_week=5),  # 6 PM Friday
        'options': {'queue': 'monitoring'}
    }
}

logger.info("Celery app configured", 
           broker=settings.celery_broker_url,
           timezone=celery_app.conf.timezone)