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
        "\"from django.contrib.auth import get_user_model; "
        "User = get_user_model(); "
        "print([(u.email, u.role, u.is_active, u.is_superuser) for u in User.objects.all()])\""
    )
    stdin, stdout, stderr = ssh.exec_command(query)
    print("USERS IN DATABASE:")
    print(stdout.read().decode('utf-8'))
    print("STDERR:")
    print(stderr.read().decode('utf-8'))
    
    ssh.close()
except Exception as e:
    print(f"Error: {e}")
