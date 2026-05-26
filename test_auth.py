import google.auth

try:
    # This automatically searches your system for the ADC credentials you just created
    credentials, project_id = google.auth.default()
    
    print("✅ Authentication Successful!")
    print(f"Active Project ID: {project_id}")
    print(f"Credential Type: {type(credentials).__name__}")

except Exception as e:
    print("❌ Authentication Failed!")
    print(f"Error: {e}")