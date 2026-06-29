import paramiko

hostname = '72.61.233.159'
username = 'root'
password = 'rLsYd+@eEsJ.W04#'

def run_cmd(ssh, cmd):
    print(f"\n--- Running: {cmd} ---")
    stdin, stdout, stderr = ssh.exec_command(cmd)
    out = stdout.read().decode('utf-8', errors='replace')
    err = stderr.read().decode('utf-8', errors='replace')
    if out:
        print("STDOUT:")
        print(out)
    if err:
        print("STDERR:")
        print(err)

try:
    ssh = paramiko.SSHClient()
    ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    ssh.connect(hostname, username=username, password=password, timeout=10)
    print("Successfully connected via SSH!")
    
    # Check OS
    run_cmd(ssh, "uname -a; cat /etc/os-release")
    
    # Check Nginx config and sites enabled
    run_cmd(ssh, "ls -la /etc/nginx/sites-enabled/")
    
    # Check current Python and Node versions
    run_cmd(ssh, "python3 --version; node -v; pm2 -v")
    
    # Check systemctl services running (look for gunicorn, uwsgi, daphne)
    run_cmd(ssh, "systemctl list-units --type=service --state=running | grep -iE 'gunicorn|uwsgi|daphne|node|pm2|crm|dps'")
    
    # Check PostgreSQL
    run_cmd(ssh, "systemctl status postgresql | head -n 5; psql -V")

    ssh.close()
except Exception as e:
    print(f"Error: {e}")
