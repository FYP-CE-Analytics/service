import sys
from celery import Celery
import os
from dotenv import load_dotenv
load_dotenv()
sys.path.append(os.path.join(os.path.dirname(__file__), 'app'))
# Create Celery instance
app = Celery('ed_summarizer',
             broker=os.getenv('CELERY_BROKER_URL', 'redis://localhost:6379/0'),
             backend=os.getenv('CELERY_RESULT_BACKEND', 'redis://localhost:6379/0'))
app.conf.imports = (['app.tasks.fetch_insert_to_vector_db_tasks',
                    'app.tasks.thread_clustering_tasks',
                    'app.tasks.agents_tasks'])
if __name__ == "__main__":
    app.worker_main(['worker', '--loglevel=info'])
