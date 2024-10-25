# gunicorn_conf.py
from multiprocessing import cpu_count

# Gunicorn config
bind = "0.0.0.0:8000"
workers = cpu_count() * 2 + 1  # Number of worker processes
worker_class = "uvicorn.workers.UvicornWorker"  # Use Uvicorn worker class
max_requests = (
    50000  # Maximum number of requests a worker will process before restarting
)
max_requests_jitter = 2000  # Adds randomness to max_requests to prevent all workers from restarting at once
timeout = 30  # Worker timeout
keepalive = 30  # Keep-alive timeout
backlog = 2048  # Connection queue size

# Uvicorn-specific configs
worker_connections = 1000  # Maximum number of concurrent connections per worker
forwarded_allow_ips = "*"  # Allow forwarded requests from any IP

# Optional logging configuration
accesslog = "-"  # Log to stdout
errorlog = "-"  # Log to stdout
loglevel = "info"
