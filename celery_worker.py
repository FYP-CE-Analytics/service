from celery import Celery

# Create Celery instance
celery_app = Celery('ed_summariser')

# Configure Celery
celery_app.conf.update(
    broker_url='redis://localhost:6379/0',
    result_backend='redis://localhost:6379/0',
    # Using pickle for scientific computing objects (numpy arrays, etc)
    task_serializer='pickle',
    accept_content=['json', 'pickle'],
    result_serializer='pickle',  # Using pickle for results containing clusters
    timezone='UTC',
    enable_utc=True,
    task_routes={
        # Dedicated queue
        'app.tasks.clustering_tasks.*': {'queue': 'clustering'},
        'app.tasks.*': {'queue': 'default'},
    },
    worker_prefetch_multiplier=1,  # Prevents workers from taking too many tasks at once
    # Acknowledges tasks after completion (safer for long-running tasks)
    task_acks_late=True,
)

# Auto-discover tasks in registered app modules
celery_app.autodiscover_tasks(['app.tasks'])

# Configure Celery Beat schedule for periodic tasks
celery_app.conf.beat_schedule = {
    'run-clustering-daily': {
        'task': 'app.tasks.clustering_tasks.daily_clustering_analysis',
        'schedule': 24 * 60 * 60,  # 24 hours
    },
    'update-user-clusters-hourly': {
        'task': 'app.tasks.clustering_tasks.assign_users_to_clusters',
        'schedule': 60 * 60,  # 1 hour
    },
}
