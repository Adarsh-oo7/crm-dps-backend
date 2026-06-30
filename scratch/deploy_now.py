import paramiko
import sys

hostname = '72.61.233.159'
username = 'root'
password = 'rLsYd+@eEsJ.W04#'

def run_cmd(ssh, cmd):
    print(f"\n>>> Executing: {cmd}")
    stdin, stdout, stderr = ssh.exec_command(cmd)
    
    # Read outputs blockingly
    out = stdout.read().decode('utf-8', errors='replace')
    err = stderr.read().decode('utf-8', errors='replace')
    
    if out.strip():
        print("STDOUT:")
        print(out)
    if err.strip():
        print("STDERR:")
        print(err)
        
    exit_status = stdout.channel.recv_exit_status()
    print(f"Exit status: {exit_status}")
    return exit_status == 0

try:
    ssh = paramiko.SSHClient()
    ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    ssh.connect(hostname, username=username, password=password, timeout=15)
    print("Connected successfully to VPS!")
    
    # 1. Pull latest code from main
    run_cmd(ssh, "cd /var/www/dps-os/backend && git fetch origin && git reset --hard origin/main")
    
    # 2. Run Django migrations
    migration_cmd = (
        "export DJANGO_SETTINGS_MODULE=config.settings.production && "
        "/var/www/dps-os/venv/bin/python /var/www/dps-os/backend/manage.py migrate --noinput"
    )
    run_cmd(ssh, migration_cmd)
    
    # 3. Collect static files
    static_cmd = (
        "export DJANGO_SETTINGS_MODULE=config.settings.production && "
        "/var/www/dps-os/venv/bin/python /var/www/dps-os/backend/manage.py collectstatic --noinput"
    )
    run_cmd(ssh, static_cmd)
    
    # 4. Restart Gunicorn service
    run_cmd(ssh, "systemctl restart dps-os")
    
    # 5. Reload Nginx
    run_cmd(ssh, "nginx -t && systemctl reload nginx")
    
    print("\nDEPLOYMENT COMPLETED SUCCESSFULLY!")
    ssh.close()
except Exception as e:
    print(f"Error during deployment: {e}")
