import os
import time
import requests
import base64
from datetime import datetime
from dotenv import load_dotenv
from app import database

load_dotenv()

class FitbitClient:
    def __init__(self):
        self.client_id = os.getenv("FITBIT_CLIENT_ID")
        self.client_secret = os.getenv("FITBIT_CLIENT_SECRET")
        self.tokens = self.load_tokens()

    def load_tokens(self):
        """Loads tokens from the JSON file."""
        tokens = database.get_tokens()
        if not tokens:
            print("Error: Tokens not found in DB. Run get_tokens.py first.")
        return tokens
        
    def save_tokens(self, tokens):
        """Updates SQLite with new tokens."""
        expires_at = time.time() + tokens.get("expires_in",28800)
        database.update_tokens(tokens["access_token"],tokens["refresh_token"],expires_at)
        self.tokens = self.load_tokens()
        print("[Fitbit] Tokens refreshed and saved to SQLite.")


    def get_sleep_today(self):
        """Fetches total sleep minutes for today."""
        if not self.ensure_active_token(): return 0
        
        date_str = datetime.now().strftime("%Y-%m-%d")
        url = f"https://api.fitbit.com/1.2/user/-/sleep/date/{date_str}.json"
        
        print(f"\n💤 [Fitbit] Fetching sleep for {date_str}...")
        response = requests.get(url, headers=self._get_headers())
        
        if response.status_code == 200:
            data = response.json()

            summary = data.get("summary", {})
            total_minutes = summary.get("totalMinutesAsleep", 0)
            
            print(f"✅ [Fitbit] Sleep Found: {total_minutes} mins")
            return total_minutes
        else:
            print(f"❌ [Fitbit] Sleep Error: {response.text}")
            return 0

    def _get_headers(self):
        if not self.tokens: return {}
        return {"Authorization": f"Bearer {self.tokens['access_token']}"}

    def ensure_active_token(self):
        """Checks expiry and refreshes if needed."""
        if not self.tokens: return False

        if time.time() > self.tokens.get("expires_at", 0) - 300:
            print("🔄 [Fitbit] Token expired. Refreshing...")
            return self.refresh_token()
        return True

    def refresh_token(self):
        url = "https://api.fitbit.com/oauth2/token"
        auth_str = f"{self.client_id}:{self.client_secret}"
        b64_auth = base64.b64encode(auth_str.encode()).decode()
        
        headers = {"Authorization": f"Basic {b64_auth}", "Content-Type": "application/x-www-form-urlencoded"}
        data = {"grant_type": "refresh_token", "refresh_token": self.tokens["refresh_token"]}
        
        response = requests.post(url, headers=headers, data=data)
        if response.status_code == 200:
            self.save_tokens(response.json())
            return True
        else:
            print(f"❌ [Fitbit] Refresh Failed: {response.text}")
            return False

    def get_calories_today(self):
            if not self.ensure_active_token(): return 0
            
            date_str = datetime.now().strftime("%Y-%m-%d")
            url = f"https://api.fitbit.com/1/user/-/activities/date/{date_str}.json"
            
            print(f"\n📡 [Fitbit] Fetching data for {date_str}...")
            response = requests.get(url, headers=self._get_headers())
            
            if response.status_code == 200:
                cal = response.json().get("summary", {}).get("caloriesOut", 0)
                print(f"✅ [Fitbit] Active Calories Burned: {cal}")
                return cal
            elif response.status_code == 401:
                print("⚠️ [Fitbit] Unexpected 401. Forcing refresh...")
                if self.refresh_token():
                    return self.get_calories_today() 
            else:
                print(f"❌ [Fitbit] API Error: {response.text}")
                return 0
