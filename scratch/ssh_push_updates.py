import paramiko

hostname = '72.61.233.159'
username = 'root'
password = 'rLsYd+@eEsJ.W04#'

files_to_upload = {
    r'd:\CRM\backend\apps\accounts\models.py': '/var/www/dps-os/backend/apps/accounts/models.py',
    r'd:\CRM\backend\apps\accounts\migrations\0005_userotp.py': '/var/www/dps-os/backend/apps/accounts/migrations/0005_userotp.py',
    r'd:\CRM\backend\apps\accounts\views.py': '/var/www/dps-os/backend/apps/accounts/views.py',
    r'd:\CRM\backend\apps\accounts\urls.py': '/var/www/dps-os/backend/apps/accounts/urls.py',
}

try:
    ssh = paramiko.SSHClient()
    ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    ssh.connect(hostname, username=username, password=password, timeout=15)
    print("Connected successfully via SSH!")
    
    sftp = ssh.open_sftp()
    
    for local, remote in files_to_upload.items():
        print(f"Uploading {local} to {remote}...")
        sftp.put(local, remote)
        print("Success!")
        
    sftp.close()
    
    # Run migrations on VPS
    print("Running migrations on VPS...")
    migration_cmd = (
        "export DJANGO_SETTINGS_MODULE=config.settings.production && "
        "/var/www/dps-os/venv/bin/python /var/www/dps-os/backend/manage.py migrate --noinput"
    )
    stdin, stdout, stderr = ssh.exec_command(migration_cmd)
    print("MIGRATIONS STDOUT:")
    print(stdout.read().decode('utf-8'))
    print("MIGRATIONS STDERR:")
    print(stderr.read().decode('utf-8'))
    
    # Seeding superuser: update 'admin@digitalprod.com' or create 'digitalproductkerala@gmail.com'
    print("Updating/Seeding superuser 'digitalproductkerala@gmail.com' on VPS...")
    update_su_script = (
        "from django.contrib.auth import get_user_model; "
        "User = get_user_model(); "
        "User.objects.filter(email='admin@digitalprod.com').delete(); "
        "User.objects.filter(email='digitalproductkerala@gmail.com').exists() or "
        "User.objects.create_superuser('digitalproductkerala@gmail.com', 'Adarsh@2001', full_name='System Administrator', role='superadmin'); "
        "su = User.objects.get(email='digitalproductkerala@gmail.com'); "
        "su.set_password('Adarsh@2001'); "
        "su.role = 'superadmin'; "
        "su.save()"
    )
    su_cmd = (
        "export DJANGO_SETTINGS_MODULE=config.settings.production && "
        f'/var/www/dps-os/venv/bin/python /var/www/dps-os/backend/manage.py shell -c "{update_su_script}"'
    )
    stdin, stdout, stderr = ssh.exec_command(su_cmd)
    stdout.read() # wait
    print("Superuser configuration completed!")
    
    # Restart Gunicorn service to load updated settings
    print("Restarting Gunicorn service...")
    stdin, stdout, stderr = ssh.exec_command("systemctl restart dps-os")
    stdout.read() # Wait for completion
    print("Service restarted successfully!")
    
    ssh.close()
    print("File synchronization and server reload complete!")
except Exception as e:
    print(f"Error during file sync: {e}")
