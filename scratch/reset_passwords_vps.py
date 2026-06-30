import paramiko

hostname = '72.61.233.159'
username = 'root'
password = '/oO/8esUq)OH/sej'

script_content = """from django.contrib.auth import get_user_model
User = get_user_model()
u1 = User.objects.filter(email='adarshbini2019@gmail.com').first()
u2 = User.objects.filter(email='digitalproductkerala@gmail.com').first()
if u1:
    u1.set_password('adarsh@00')
    u1.save()
    print('Reset adarshbini2019 password successfully!')
if u2:
    u2.set_password('Adarsh@2001')
    u2.save()
    print('Reset digitalproductkerala password successfully!')
"""

try:
    ssh = paramiko.SSHClient()
    ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    ssh.connect(hostname, username=username, password=password, timeout=15)
    print("Connected successfully to VPS!")

    cmd = "export DJANGO_SETTINGS_MODULE=config.settings.production && /var/www/dps-os/venv/bin/python /var/www/dps-os/backend/manage.py shell"
    stdin, stdout, stderr = ssh.exec_command(cmd)
    
    # Write the script block to Django shell stdin
    stdin.write(script_content)
    stdin.close() # Send EOF

    out = stdout.read().decode('utf-8', errors='replace')
    err = stderr.read().decode('utf-8', errors='replace')

    print("STDOUT:")
    print(out)
    if err.strip():
        print("STDERR:")
        print(err)

    ssh.close()
except Exception as e:
    print(f"Error: {e}")
