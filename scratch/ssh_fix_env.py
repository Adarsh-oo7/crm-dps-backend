import paramiko

hostname = '72.61.233.159'
username = 'root'
password = 'rLsYd+@eEsJ.W04#'

try:
    ssh = paramiko.SSHClient()
    ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    ssh.connect(hostname, username=username, password=password, timeout=10)
    
    # Check current .env
    print("Reading remote .env...")
    stdin, stdout, stderr = ssh.exec_command("cat /var/www/dps-os/backend/.env")
    env_content = stdout.read().decode('utf-8')
    print(env_content)
    
    # Append DJANGO_SETTINGS_MODULE if not present
    if 'DJANGO_SETTINGS_MODULE' not in env_content:
        print("Appending DJANGO_SETTINGS_MODULE to remote .env...")
        new_env_content = env_content + "\nDJANGO_SETTINGS_MODULE=config.settings.production\n"
        ssh.exec_command(f'cat << \'EOF\' > /var/www/dps-os/backend/.env\n{new_env_content}EOF')
        print("Remote .env updated!")
    
    # Restart Gunicorn service
    print("Restarting Gunicorn...")
    stdin, stdout, stderr = ssh.exec_command("systemctl restart dps-os")
    stdout.read()
    print("Gunicorn restarted successfully!")
    
    ssh.close()
except Exception as e:
    print(f"Error: {e}")
