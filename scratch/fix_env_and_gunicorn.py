import paramiko

hostname = '72.61.233.159'
username = 'root'
password = '/oO/8esUq)OH/sej'

env_content = (
    "SECRET_KEY=django-insecure-prod-key-crm-dps-os-321\n"
    "DEBUG=False\n"
    "DJANGO_SETTINGS_MODULE=config.settings.production\n"
    "ALLOWED_HOSTS=crm-api.digitalproductsolutions.in,72.61.233.159\n"
    "CORS_ALLOWED_ORIGINS=https://dps-os.vercel.app,http://localhost:5173,https://crm.digitalproductsolutions.in\n"
    "DATABASE_URL=postgresql://dps_user:DpsSecure@123_456@localhost:5432/dps_os_db\n"
    "EMAIL_HOST_USER=digitalproductkerala@gmail.com\n"
    "EMAIL_HOST_PASSWORD=ruzv oifw ibsu khdk\n"
    "DEFAULT_FROM_EMAIL=digitalproductkerala@gmail.com\n"
    "OPENWA_URL=http://localhost:3000\n"
    "OPENWA_TOKEN=\n"
    "FCM_SERVER_KEY=\n"
)

try:
    ssh = paramiko.SSHClient()
    ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    ssh.connect(hostname, username=username, password=password, timeout=15)
    print("Connected successfully to VPS!")

    # Write correct .env file
    print("Writing production .env file with settings module to VPS...")
    sftp = ssh.open_sftp()
    with sftp.open('/var/www/dps-os/backend/.env', 'w') as f:
        f.write(env_content)
    sftp.close()
    print("Production .env file written successfully!")

    # Run deployment commands
    commands = [
        "export DJANGO_SETTINGS_MODULE=config.settings.production && /var/www/dps-os/venv/bin/python /var/www/dps-os/backend/manage.py migrate --noinput",
        "systemctl restart dps-os",
        "systemctl status dps-os --no-pager"
    ]

    for cmd in commands:
        print(f"\nExecuting: {cmd}")
        stdin, stdout, stderr = ssh.exec_command(cmd)
        out = stdout.read().decode('utf-8', errors='replace')
        err = stderr.read().decode('utf-8', errors='replace')
        if out.strip():
            print(f"STDOUT:\n{out}")
        if err.strip():
            print(f"STDERR:\n{err}")

    ssh.close()
    print("\nGUNICORN SETTINGS MODULE UPDATE COMPLETED!")
except Exception as e:
    print(f"Error: {e}")
