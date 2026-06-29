import paramiko
import sys

hostname = '72.61.233.159'
username = 'root'
password = 'rLsYd+@eEsJ.W04#'

# Ensure stdout uses replacement for non-encodable chars on Windows
def safe_print(text):
    try:
        sys.stdout.buffer.write(text.encode(sys.stdout.encoding or 'utf-8', errors='replace'))
        sys.stdout.buffer.write(b'\n')
        sys.stdout.flush()
    except Exception:
        print(text.encode('ascii', errors='replace').decode('ascii'))

def run_cmd(ssh, cmd):
    safe_print(f"\n>>> Executing: {cmd}")
    stdin, stdout, stderr = ssh.exec_command(cmd)
    
    # Read outputs blockingly
    out = stdout.read().decode('utf-8', errors='replace')
    err = stderr.read().decode('utf-8', errors='replace')
    
    if out.strip():
        safe_print("STDOUT:")
        safe_print(out)
    if err.strip():
        safe_print("STDERR:")
        safe_print(err)
        
    exit_status = stdout.channel.recv_exit_status()
    safe_print(f"Exit status: {exit_status}")
    return exit_status == 0

try:
    ssh = paramiko.SSHClient()
    ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    ssh.connect(hostname, username=username, password=password, timeout=15)
    safe_print("Connected successfully to VPS!")
    
    # 1. Create database and user in PostgreSQL
    db_setup_cmd = (
        'sudo -u postgres psql -c "CREATE USER dps_user WITH PASSWORD \'DpsSecure@123_456\';" || true; '
        'sudo -u postgres psql -c "CREATE DATABASE dps_os_db OWNER dps_user;" || true; '
        'sudo -u postgres psql -c "GRANT ALL PRIVILEGES ON DATABASE dps_os_db TO dps_user;" || true;'
    )
    run_cmd(ssh, db_setup_cmd)
    
    # 2. Setup project folder
    run_cmd(ssh, "mkdir -p /var/www/dps-os && chmod 755 /var/www/dps-os")
    
    # 3. Clone git repository
    # If folder already exists, pull instead
    check_repo = run_cmd(ssh, "ls -la /var/www/dps-os/backend/manage.py")
    if check_repo:
        safe_print("Backend repo already exists. Pulling latest main...")
        run_cmd(ssh, "cd /var/www/dps-os/backend && git reset --hard && git pull origin main")
    else:
        safe_print("Cloning repo...")
        run_cmd(ssh, "rm -rf /var/www/dps-os/backend")
        run_cmd(ssh, "git clone https://github.com/Adarsh-oo7/crm-dps-backend.git /var/www/dps-os/backend")
        
    # 4. Create virtualenv
    run_cmd(ssh, "python3 -m venv /var/www/dps-os/venv")
    
    # 5. Install dependencies
    run_cmd(ssh, "/var/www/dps-os/venv/bin/pip install --quiet --upgrade pip")
    run_cmd(ssh, "/var/www/dps-os/venv/bin/pip install --quiet -r /var/www/dps-os/backend/requirements.txt")
    run_cmd(ssh, "/var/www/dps-os/venv/bin/pip install --quiet gunicorn whitenoise")
    
    # 6. Write production .env file
    env_content = (
        "SECRET_KEY=django-insecure-prod-key-crm-dps-os-321\n"
        "DEBUG=False\n"
        "ALLOWED_HOSTS=crm-api.digitalproductsolutions.in,72.61.233.159\n"
        "CORS_ALLOWED_ORIGINS=https://dps-os.vercel.app,http://localhost:5173\n"
        "DATABASE_URL=postgresql://dps_user:DpsSecure@123_456@localhost:5432/dps_os_db\n"
        "EMAIL_HOST_USER=digitalproductkerala@gmail.com\n"
        "EMAIL_HOST_PASSWORD=ruzv oifw ibsu khdk\n"
        "DEFAULT_FROM_EMAIL=digitalproductkerala@gmail.com\n"
        "OPENWA_URL=http://localhost:3000\n"
        "OPENWA_TOKEN=\n"
        "FCM_SERVER_KEY=\n"
    )
    
    run_cmd(ssh, f'cat << \'EOF\' > /var/www/dps-os/backend/.env\n{env_content}EOF')
    run_cmd(ssh, "chmod 600 /var/www/dps-os/backend/.env")
    
    # 7. Create log, media and static dirs
    run_cmd(ssh, "mkdir -p /var/www/dps-os/backend/logs /var/www/dps-os/backend/media /var/www/dps-os/backend/staticfiles /var/www/dps-os/backend/cache")
    run_cmd(ssh, "chmod -R 777 /var/www/dps-os/backend/logs /var/www/dps-os/backend/media /var/www/dps-os/backend/cache")

    # 8. Run migrations & collectstatic
    migration_cmd = (
        "export DJANGO_SETTINGS_MODULE=config.settings.production && "
        "/var/www/dps-os/venv/bin/python /var/www/dps-os/backend/manage.py migrate --noinput"
    )
    run_cmd(ssh, migration_cmd)
    
    static_cmd = (
        "export DJANGO_SETTINGS_MODULE=config.settings.production && "
        "/var/www/dps-os/venv/bin/python /var/www/dps-os/backend/manage.py collectstatic --noinput"
    )
    run_cmd(ssh, static_cmd)
    
    # 9. Create default superuser if none exists
    create_superuser_script = (
        "from django.contrib.auth import get_user_model; "
        "User = get_user_model(); "
        "User.objects.filter(email='admin@digitalprod.com').exists() or "
        "User.objects.create_superuser('admin@digitalprod.com', 'adminpass', full_name='System Administrator', role='superadmin')"
    )
    su_cmd = (
        "export DJANGO_SETTINGS_MODULE=config.settings.production && "
        f'/var/www/dps-os/venv/bin/python /var/www/dps-os/backend/manage.py shell -c "{create_superuser_script}"'
    )
    run_cmd(ssh, su_cmd)
    
    # 10. Install Gunicorn Systemd service
    service_content = """[Unit]
Description=DPS OS Gunicorn daemon
After=network.target postgresql.service

[Service]
User=root
Group=www-data
WorkingDirectory=/var/www/dps-os/backend
EnvironmentFile=/var/www/dps-os/backend/.env
ExecStart=/var/www/dps-os/venv/bin/gunicorn \\
    --workers 3 \\
    --bind 127.0.0.1:8006 \\
    --timeout 120 \\
    config.wsgi:application

[Install]
WantedBy=multi-user.target
"""
    run_cmd(ssh, f'cat << \'EOF\' > /etc/systemd/system/dps-os.service\n{service_content}EOF')
    run_cmd(ssh, "systemctl daemon-reload && systemctl enable dps-os && systemctl restart dps-os")
    
    # 11. Configure Nginx site
    nginx_content = """server {
    listen 80;
    server_name crm-api.digitalproductsolutions.in;

    location /static/ {
        alias /var/www/dps-os/backend/staticfiles/;
        expires 30d;
    }

    location /media/ {
        alias /var/www/dps-os/backend/media/;
        expires 7d;
    }

    location / {
        proxy_pass http://127.0.0.1:8006;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }
}
"""
    run_cmd(ssh, f'cat << \'EOF\' > /etc/nginx/sites-available/dps-os\n{nginx_content}EOF')
    run_cmd(ssh, "ln -sf /etc/nginx/sites-available/dps-os /etc/nginx/sites-enabled/dps-os")
    
    # Test nginx and reload
    run_cmd(ssh, "nginx -t && systemctl reload nginx")
    
    # 12. Run Certbot for SSL
    run_cmd(ssh, "certbot --nginx -d crm-api.digitalproductsolutions.in --non-interactive --agree-tos -m digitalproductkerala@gmail.com || true")

    safe_print("\nDEPLOYMENT COMPLETED SUCCESSFULLY!")
    ssh.close()
except Exception as e:
    safe_print(f"Error during deployment: {e}")
