import paramiko

hostname = '72.61.233.159'
username = 'root'
password = 'rLsYd+@eEsJ.W04#'

files_to_upload = {
    r'd:\CRM\backend\config\settings\base.py': '/var/www/dps-os/backend/config/settings/base.py',
    r'd:\CRM\backend\scripts\cron_jobs.py': '/var/www/dps-os/backend/scripts/cron_jobs.py',
    r'd:\CRM\backend\gunicorn.conf.py': '/var/www/dps-os/backend/gunicorn.conf.py'
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
    
    # Restart Gunicorn service to load updated settings
    print("Restarting Gunicorn service...")
    stdin, stdout, stderr = ssh.exec_command("systemctl restart dps-os")
    stdout.read() # Wait for completion
    print("Service restarted successfully!")
    
    ssh.close()
    print("File synchronization complete!")
except Exception as e:
    print(f"Error during file sync: {e}")
