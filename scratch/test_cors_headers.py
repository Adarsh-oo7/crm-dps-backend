import requests

url = 'https://crm-api.digitalproductsolutions.in/api/auth/login/'
origin = 'https://crm.digitalproductsolutions.in'

print("--- Testing Live CORS Headers ---")
print(f"Requesting: {url}")
print(f"Origin: {origin}")

try:
    # Send OPTIONS request first (preflight)
    res_options = requests.options(
        url,
        headers={
            'Origin': origin,
            'Access-Control-Request-Method': 'POST',
            'Access-Control-Request-Headers': 'Content-Type'
        },
        timeout=10
    )
    print(f"\nOPTIONS Response Code: {res_options.status_code}")
    print("OPTIONS Headers:")
    for k, v in res_options.headers.items():
        if 'access-control' in k.lower():
            print(f"  {k}: {v}")
            
    # Send POST request
    res_post = requests.post(
        url,
        json={'email': 'test@test.com', 'password': 'test'},
        headers={
            'Origin': origin,
            'Content-Type': 'application/json'
        },
        timeout=10
    )
    print(f"\nPOST Response Code: {res_post.status_code}")
    print("POST Headers:")
    for k, v in res_post.headers.items():
        if 'access-control' in k.lower():
            print(f"  {k}: {v}")
            
except Exception as e:
    print(f"Error: {e}")
