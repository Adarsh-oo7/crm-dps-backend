# ─────────────────────────────────────────────────────────────────────────────
# Gunicorn Configuration — /home/dps/dps-os/backend/gunicorn.conf.py
# ─────────────────────────────────────────────────────────────────────────────
import multiprocessing

# Binding
bind = "127.0.0.1:8000"

# Workers — (2 * CPU cores) + 1 is the recommended formula
workers = multiprocessing.cpu_count() * 2 + 1
worker_class = "sync"
worker_connections = 1000
timeout = 120
keepalive = 5

# Process name
proc_name = "dps_os"

# Logging
accesslog = "/home/dps/dps-os/backend/logs/gunicorn_access.log"
errorlog  = "/home/dps/dps-os/backend/logs/gunicorn_error.log"
loglevel  = "warning"

# Reload on code changes (disable in production once stable)
reload = False

# Security
limit_request_line = 4094
limit_request_fields = 100
forwarded_allow_ips = "127.0.0.1"
