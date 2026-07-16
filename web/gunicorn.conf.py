import os


bind = f"0.0.0.0:{os.getenv('PORT', '5000')}"
workers = int(os.getenv("WEB_WORKERS", "2"))
threads = int(os.getenv("WEB_THREADS", "4"))
worker_class = "gthread"
timeout = int(os.getenv("WEB_REQUEST_TIMEOUT_SECONDS", "120"))
graceful_timeout = int(os.getenv("WEB_GRACEFUL_TIMEOUT_SECONDS", "30"))
keepalive = 5
worker_tmp_dir = os.getenv("WEB_WORKER_TMP_DIR", "/dev/shm")
errorlog = "-"
accesslog = None
capture_output = True
preload_app = False
