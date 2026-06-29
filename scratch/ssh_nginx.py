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
    
    # Get all active nginx site configs
    files_str = run_cmd(ssh, "find /etc/nginx/sites-enabled/ -type l -o -type f")
    files = [f.strip() for f in files_str.split('\n') if f.strip()]
    
    for f in files:
        print(f"\n========================================\nFile: {f}\n========================================\n")
        content = run_cmd(ssh, f"cat {f}")
        # Print only server_name and proxy_pass lines to keep it clean
        for line in content.split('\n'):
            line_strip = line.strip()
            if 'server_name' in line_strip or 'proxy_pass' in line_strip or 'listen' in line_strip:
                print(line_strip)
                
    ssh.close()
except Exception as e:
    print(f"Error: {e}")
