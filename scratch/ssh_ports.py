import paramiko

hostname = '72.61.233.159'
username = 'root'
password = 'rLsYd+@eEsJ.W04#'

def run_cmd(ssh, cmd):
    stdin, stdout, stderr = ssh.exec_command(cmd)
    return stdout.read().decode('utf-8', errors='replace')

try:
    ssh = paramiko.SSHClient()
    ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    ssh.connect(hostname, username=username, password=password, timeout=10)
    
    print("Ports listening:")
    print(run_cmd(ssh, "ss -lntp"))
    
    print("\nPostgres status:")
    print(run_cmd(ssh, "pg_isready"))
    
    print("\nLocal users:")
    print(run_cmd(ssh, "cut -d: -f1 /etc/passwd | tail -n 15"))

    ssh.close()
except Exception as e:
    print(f"Error: {e}")
