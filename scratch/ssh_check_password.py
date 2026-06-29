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
        "su = User.objects.get(email='digitalproductkerala@gmail.com'); "
        "print('CHECK_PASS:', su.check_password('Adarsh@2001'))\""
    )
    stdin, stdout, stderr = ssh.exec_command(query)
    print("PASSWORD CHECK:")
    print(stdout.read().decode('utf-8'))
    print("STDERR:")
    print(stderr.read().decode('utf-8'))
    
    ssh.close()
except Exception as e:
    print(f"Error: {e}")
