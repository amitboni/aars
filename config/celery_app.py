"""config/celery_app.py — Celery configuration."""
from celery import Celery
from celery.schedules import crontab

from config.settings import settings

celery_app = Celery(
    "aars",
    broker=settings.CELERY_BROKER_URL,
    include=[
        "tasks.signal_processing",
        "tasks.decision_engine",
        "tasks.playbook_execution",
        "tasks.adm_briefing",
        "tasks.integration_sync",
        "tasks.analytics_aggregation",
    ],
)

celery_app.conf.update(
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    timezone="UTC",
    enable_utc=True,
    task_track_started=True,
    task_acks_late=True,
    worker_prefetch_multiplier=1,
)

celery_app.conf.beat_schedule = {
    "process-pending-signals": {
        "task": "tasks.signal_processing.process_pending_signals",
        "schedule": 60.0,  # every minute
    },
    "execute-due-playbook-steps": {
        "task": "tasks.playbook_execution.execute_due_playbook_steps",
        "schedule": 60.0,  # every minute
    },
    "decision-engine-batch": {
        "task": "tasks.decision_engine.decision_engine_batch",
        "schedule": crontab(hour=1, minute=0),  # daily 01:00 UTC (before briefings)
    },
    "execute-pending-decisions": {
        "task": "tasks.decision_engine.execute_pending_decisions",
        "schedule": 60.0,  # every minute
    },
    "generate-morning-briefings": {
        "task": "tasks.adm_briefing.generate_morning_briefings",
        "schedule": crontab(hour=2, minute=0),  # daily 02:00 UTC (07:30 IST)
    },
    "generate-weekly-summaries": {
        "task": "tasks.adm_briefing.generate_weekly_summaries",
        "schedule": crontab(hour=2, minute=30, day_of_week=1),  # Monday 02:30 UTC
    },
    "analytics-weekly-aggregation": {
        "task": "tasks.analytics_aggregation.weekly_aggregation",
        "schedule": crontab(hour=4, minute=0, day_of_week=1),  # Monday 04:00 UTC
    },
    "analytics-monthly-reports": {
        "task": "tasks.analytics_aggregation.monthly_reports",
        "schedule": crontab(hour=5, minute=0, day_of_month=1),  # 1st of month 05:00 UTC
    },
    "integration-sync-daily": {
        "task": "tasks.integration_sync.sync_external_data",
        "schedule": crontab(hour=0, minute=0),  # daily 00:00 UTC
    },
}
