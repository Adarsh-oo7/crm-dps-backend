import requests
import json

base_url = 'https://crm-api.digitalproductsolutions.in'

print("--- Testing Live VPS API Connectivity ---")
print(f"Endpoint: {base_url}/api/auth/login/")

payload = {
    'email': 'admin@digitalprod.com',
    'password': 'adminpass'
}

try:
    response = requests.post(
        f"{base_url}/api/auth/login/",
        json=payload,
        headers={'Content-Type': 'application/json'},
        timeout=10
    )
    
    print(f"\nResponse Code: {response.status_code}")
    if response.status_code == 200:
        data = response.json()
        print("SUCCESS! Seeding and login verified!")
        print(f"User: {data['user']['full_name']} ({data['user']['role']})")
        print(f"Access Token length: {len(data['access'])}")
        print(f"Refresh Token length: {len(data['refresh'])}")
    else:
        print("FAIL! Login failed with response:")
        print(response.text)
except Exception as e:
    print(f"ERROR: Could not connect to API: {e}")
