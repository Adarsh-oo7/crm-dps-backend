import paramiko

hostname = '72.61.233.159'
username = 'root'
password = '/oO/8esUq)OH/sej'

try:
    ssh = paramiko.SSHClient()
    ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    ssh.connect(hostname, username=username, password=password, timeout=15)
    
    cmd = (
        "export DJANGO_SETTINGS_MODULE=config.settings.production && "
        "/var/www/dps-os/venv/bin/python /var/www/dps-os/backend/manage.py shell -c "
        "\"from django.contrib.auth import get_user_model; print([u.email for u in get_user_model().objects.all()])\""
    )
    
    stdin, stdout, stderr = ssh.exec_command(cmd)
    out = stdout.read().decode('utf-8', errors='replace')
    err = stderr.read().decode('utf-8', errors='replace')
    
    print("VPS Output:")
    print(out)
    if err.strip():
        print("VPS Errors:")
        print(err)
        
    ssh.close()
except Exception as e:
    print(f"Error: {e}")
