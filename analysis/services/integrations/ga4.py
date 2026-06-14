import os
import datetime
import requests
from django.conf import settings
from django.utils import timezone
from google.analytics.data_v1beta import BetaAnalyticsDataClient
from google.analytics.data_v1beta.types import (
    DateRange,
    Dimension,
    Metric,
    RunReportRequest,
)
from google.oauth2.credentials import Credentials

class GA4Service:
    """
    Service to interact with the Google Analytics 4 API.
    Handles automatic OAuth2 token refreshing via the UserIntegration model.
    """
    
    def __init__(self, user_integration=None, property_id=None, access_token=None):
        # 1. Determine Property ID and get a guaranteed valid token
        if user_integration:
            self.property_id = user_integration.ga4_property_id
            self.access_token = self._get_valid_token(user_integration)
        else:
            # Fallback for manual overrides or server-to-server credentials
            self.property_id = property_id or os.environ.get("GA4_PROPERTY_ID")
            self.access_token = access_token
        
        if not self.property_id:
            print("WARNING: GA4_PROPERTY_ID is not set. Real GA4 data will fail.")
            self.client = None
            return
            
        # 2. Initialize the client with the valid token
        try:
            if self.access_token:
                credentials = Credentials(token=self.access_token)
                self.client = BetaAnalyticsDataClient(credentials=credentials)
            else:
                self.client = BetaAnalyticsDataClient()
        except Exception as e:
            print(f"Failed to initialize GA4 Client. Error: {e}")
            self.client = None

    def _get_valid_token(self, integration):
        """
        Checks if the token is expired. If so, uses the refresh token to get 
        a new access token and saves it to the database.
        """
        if not integration.ga4_access_token:
            return None

        # If token is expired or expires in the next 5 mins, refresh it
        if not integration.ga4_token_expiry or integration.ga4_token_expiry <= timezone.now() + timezone.timedelta(minutes=5):
            
            if not integration.ga4_refresh_token:
                print("ERROR: Token expired but no refresh token available.")
                return None
                
            print("Refreshing GA4 Access Token...")
            response = requests.post('https://oauth2.googleapis.com/token', data={
                'client_id': settings.GOOGLE_CLIENT_ID, # Ensure this is in your settings.py
                'client_secret': settings.CLIENT_SECRET, # Ensure this is in your settings.py
                'refresh_token': integration.ga4_refresh_token,
                'grant_type': 'refresh_token'
            }, timeout=10)

            if response.status_code == 200:
                data = response.json()
                integration.ga4_access_token = data['access_token']
                # Google returns 'expires_in' in seconds (usually 3599)
                integration.ga4_token_expiry = timezone.now() + timezone.timedelta(seconds=data['expires_in'])
                integration.save()
            else:
                print(f"Failed to refresh GA4 token: {response.text}")
                return None

        return integration.ga4_access_token

    def get_traffic_last_30_days(self) -> list[dict]:
        """
        Fetches daily active users over the last 30 days.
        Returns a list of dicts suitable for the frontend chart.
        """
        if not self.client or not self.property_id:
            return []

        request = RunReportRequest(
            property=f"properties/{self.property_id}",
            dimensions=[Dimension(name="date")],
            metrics=[Metric(name="activeUsers")],
            date_ranges=[DateRange(start_date="30daysAgo", end_date="today")],
        )
        
        try:
            response = self.client.run_report(request)
            
            traffic_data = []
            for row in response.rows:
                date_str = row.dimension_values[0].value # Format: "YYYYMMDD"
                users = int(row.metric_values[0].value)
                
                # Format date for frontend
                year = date_str[0:4]
                month = date_str[4:6]
                day = date_str[6:8]
                date_obj = datetime.date(int(year), int(month), int(day))
                display_date = date_obj.strftime("%b %d") # e.g. "Apr 15"
                
                traffic_data.append({
                    "date": date_str,
                    "users": users,
                    "displayDate": display_date
                })
            
            # The API might not return sorted by date, so let's ensure it is sorted chronologically
            traffic_data.sort(key=lambda x: x["date"])
            return traffic_data

        except Exception as e:
            print(f"Error fetching GA4 traffic data: {e}")
            return []

    def get_traffic_velocity(self, traffic_data: list[dict]) -> str:
        """
        Calculates if traffic is trending up, down, or flat based on the last 30 days data.
        Compares the first 15 days vs the last 15 days.
        """
        if not traffic_data or len(traffic_data) < 10:
            return "flat"
            
        mid_point = len(traffic_data) // 2
        first_half_sum = sum(item["users"] for item in traffic_data[:mid_point])
        second_half_sum = sum(item["users"] for item in traffic_data[mid_point:])
        
        if first_half_sum == 0 and second_half_sum == 0:
            return "flat"
        if first_half_sum == 0:
             return "trending_up"
             
        growth = (second_half_sum - first_half_sum) / first_half_sum
        
        if growth > 0.05:
            return "trending_up"
        elif growth < -0.05:
            return "trending_down"
        else:
            return "flat"
            
    def get_fading_content(self) -> list[dict]:
        """
        Identify URLs where traffic has dropped significantly.
        """
        if not self.client or not self.property_id:
            return []
            
        return []