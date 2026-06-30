import paramiko

hostname = '72.61.233.159'
username = 'root'
password = '/oO/8esUq)OH/sej'

try:
    ssh = paramiko.SSHClient()
    ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    ssh.connect(hostname, username=username, password=password, timeout=15)
    print("Connected successfully to VPS!")

    cmd = "journalctl -u dps-os -n 40 --no-pager"
    stdin, stdout, stderr = ssh.exec_command(cmd)
    out = stdout.read().decode('utf-8', errors='replace')
    err = stderr.read().decode('utf-8', errors='replace')

    print("=== GUNICORN DAEMON LOGS ===")
    print(out)
    if err.strip():
        print("=== ERRORS ===")
        print(err)

    ssh.close()
except Exception as e:
    print(f"Error: {e}")
