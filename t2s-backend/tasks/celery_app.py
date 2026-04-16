from celery import Celery

from core.config import settings

celery_app = Celery(
    "text2sql_tasks",
    broker=settings.EFFECTIVE_CELERY_BROKER_URL,
    backend=settings.EFFECTIVE_CELERY_RESULT_BACKEND,
    include=["tasks.document_tasks"],
)

celery_app.conf.update(
    task_default_queue=settings.KB_QUEUE_NAME,
    task_serializer="json",
    result_serializer="json",
    accept_content=["json"],
    task_track_started=True,
    task_time_limit=settings.KB_TASK_TIMEOUT_SECONDS,
    task_always_eager=settings.CELERY_TASK_ALWAYS_EAGER,
    broker_connection_retry_on_startup=True,
)

