import requests
import paramiko
import time

base_url = 'https://crm-api.digitalproductsolutions.in'
hostname = '72.61.233.159'
username = 'root'
password = 'rLsYd+@eEsJ.W04#'

print("--- STEP 1: Login Request ---")
payload = {
    'email': 'digitalproductkerala@gmail.com',
    'password': 'Adarsh@2001'
}

response = requests.post(
    f"{base_url}/api/auth/login/",
    json=payload,
    headers={'Content-Type': 'application/json'},
    timeout=10
)

print(f"Status: {response.status_code}")
print(response.json())
res_data = response.json()

if not res_data.get('otp_required'):
    print("FAILED: OTP was not required for superadmin!")
    exit(1)

print("\n--- STEP 2: Fetch OTP from VPS Database ---")
ssh = paramiko.SSHClient()
ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
ssh.connect(hostname, username=username, password=password, timeout=10)

query_cmd = (
    "export DJANGO_SETTINGS_MODULE=config.settings.production && "
    "/var/www/dps-os/venv/bin/python /var/www/dps-os/backend/manage.py shell -c "
    "\"from apps.accounts.models import UserOTP; "
    "latest = UserOTP.objects.filter(purpose='login').order_by('-created_at').first(); "
    "print('OTP_VAL:' + latest.otp)\""
)
stdin, stdout, stderr = ssh.exec_command(query_cmd)
output = stdout.read().decode('utf-8')
ssh.close()

otp_val = None
for line in output.split('\n'):
    if line.startswith('OTP_VAL:'):
        otp_val = line.split(':')[1].strip()

if not otp_val:
    print("FAILED: Could not retrieve OTP value from database.")
    exit(1)

print(f"Latest Generated OTP: {otp_val}")

print("\n--- STEP 3: Verify OTP Code ---")
verify_payload = {
    'email': 'digitalproductkerala@gmail.com',
    'otp': otp_val
}
verify_response = requests.post(
    f"{base_url}/api/auth/verify-otp/",
    json=verify_payload,
    headers={'Content-Type': 'application/json'},
    timeout=10
)

print(f"Status: {verify_response.status_code}")
print(verify_response.json())
if verify_response.status_code == 200:
    print("SUCCESS! OTP Authentication Loop Verified!")
else:
    print("FAILED: OTP verification rejected.")
