import requests
import base64
import json
from config import BASE_URL, AUTH_URL

class KeyAccessClient:
    def __init__(self, client_id, client_secret, company_instance_name):
        self.client_id = client_id
        self.client_secret = client_secret
        self.company_instance_name = company_instance_name
        self.token = None
        self.base_url = BASE_URL.rstrip('/')

    def login(self):
        """Authenticate using Client Credentials Flow"""
        response = None
        try:
            # Create Basic Auth Header
            credentials = f"{self.client_id}:{self.client_secret}"
            encoded_credentials = base64.b64encode(credentials.encode()).decode()
            
            headers = {
                "Authorization": f"Basic {encoded_credentials}",
                "Content-Type": "application/json"
            }
            
            data = {
                "grant_type": "client_credentials",
                "scope": "cloud-system-rw"
            }
            
            print(f"Attempting login to {AUTH_URL}...")
            response = requests.post(AUTH_URL, headers=headers, json=data, timeout=30)
            response.raise_for_status()
            
            token_data = response.json()
            self.token = token_data.get("access_token")
            print("Login successful.")
            return True
            
        except requests.exceptions.RequestException as e:
            print(f"Login failed: {e}")
            if response is not None:
                 print(f"Response Content: {response.text}")
            return False

    def get_headers(self):
        if not self.token:
            raise Exception("Not authenticated. Call login() first.")
        return {
            "Authorization": f"Bearer {self.token}",
            "Content-Type": "application/json"
        }

    def create_event(self, event_data):
        """Create an entry or exit event"""
        url = f"{self.base_url}/logistics/{self.company_instance_name}/events"
        
        response = None
        try:
            headers = self.get_headers()
            # Added a 30 second timeout
            response = requests.post(url, headers=headers, json=event_data, timeout=30)
            response.raise_for_status()
            return response.json()
        except requests.exceptions.Timeout:
            print("Error creating event: Request timed out.")
            return None
        except requests.exceptions.RequestException as e:
            print(f"Error creating event: {e}")
            if response is not None:
                print(f"Response Content: {response.text}")
            return None
