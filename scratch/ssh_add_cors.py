import paramiko

hostname = '72.61.233.159'
username = 'root'
password = 'rLsYd+@eEsJ.W04#'

try:
    ssh = paramiko.SSHClient()
    ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    ssh.connect(hostname, username=username, password=password, timeout=10)
    
    # Read current .env
    print("Reading remote .env...")
    stdin, stdout, stderr = ssh.exec_command("cat /var/www/dps-os/backend/.env")
    env_content = stdout.read().decode('utf-8')
    print(env_content)
    
    # Modify CORS_ALLOWED_ORIGINS line
    new_lines = []
    for line in env_content.split('\n'):
        if line.startswith('CORS_ALLOWED_ORIGINS='):
            # Add the user's frontend domain
            new_lines.append("CORS_ALLOWED_ORIGINS=https://dps-os.vercel.app,http://localhost:5173,https://crm.digitalproductsolutions.in")
        else:
            new_lines.append(line)
            
    new_env_content = '\n'.join(new_lines)
    
    # Write back the .env file
    print("Writing updated .env...")
    ssh.exec_command(f'cat << \'EOF\' > /var/www/dps-os/backend/.env\n{new_env_content}EOF')
    print("Remote .env updated!")
    
    # Restart Gunicorn service to load updated settings
    print("Restarting Gunicorn...")
    stdin, stdout, stderr = ssh.exec_command("systemctl restart dps-os")
    stdout.read()
    print("Gunicorn restarted successfully!")
    
    ssh.close()
    print("CORS configuration updated successfully on live server!")
except Exception as e:
    print(f"Error: {e}")
