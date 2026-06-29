import paramiko

hostname = '72.61.233.159'
username = 'root'
password = 'rLsYd+@eEsJ.W04#'

try:
    ssh = paramiko.SSHClient()
    ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    ssh.connect(hostname, username=username, password=password, timeout=10)
    
    query = (
        "export DJANGO_SETTINGS_MODULE=config.settings.production && "
        "/var/www/dps-os/venv/bin/python /var/www/dps-os/backend/manage.py shell -c "
        "\"from django.conf import settings; "
        "print('SHELL_DB:', settings.DATABASES['default']['ENGINE'], settings.DATABASES['default'].get('NAME'))\""
    )
    stdin, stdout, stderr = ssh.exec_command(query)
    print("SHELL DATABASE CONFIG:")
    print(stdout.read().decode('utf-8'))
    print(stderr.read().decode('utf-8'))
    
    # Check Gunicorn service environment variables
    stdin, stdout, stderr = ssh.exec_command("systemctl show dps-os --property=Environment,EnvironmentFile")
    print("GUNICORN SERVICE ENV:")
    print(stdout.read().decode('utf-8'))
    
    ssh.close()
except Exception as e:
    print(f"Error: {e}")
