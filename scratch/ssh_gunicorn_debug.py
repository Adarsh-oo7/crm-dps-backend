import paramiko

hostname = '72.61.233.159'
username = 'root'
password = 'rLsYd+@eEsJ.W04#'

def run_cmd(ssh, cmd):
    print(f"\n--- Running: {cmd} ---")
    stdin, stdout, stderr = ssh.exec_command(cmd)
    print(stdout.read().decode('utf-8', errors='replace'))
    print(stderr.read().decode('utf-8', errors='replace'))

try:
    ssh = paramiko.SSHClient()
    ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    ssh.connect(hostname, username=username, password=password, timeout=10)
    
    run_cmd(ssh, "systemctl status dps-os")
    run_cmd(ssh, "journalctl -u dps-os -n 30 --no-pager")
    
    ssh.close()
except Exception as e:
    print(f"Error: {e}")
