from google.oauth2 import id_token
from google.auth.transport import requests as google_requests
from django.conf import settings
from google.analytics.data_v1beta import BetaAnalyticsDataClient
from google.analytics.data_v1beta import DateRange, Dimension, Metric, RunReportRequest
from google.oauth2.credentials import Credentials
from typing import Dict, Any, List, Optional
import requests
import os

class GoogleService:
    @staticmethod
    def exchange_auth_code(code: str) -> Optional[Dict[str, Any]]:
        try:
            response = requests.post(
                'https://oauth2.googleapis.com/token',
                data={
                    'code': code,
                    'client_id': settings.GOOGLE_CLIENT_ID,
                    'client_secret': os.getenv('CLIENT_SECRET'),
                    'redirect_uri': f"{settings.FRONTEND_URL}/auth/callback/google",
                    'grant_type': 'authorization_code',
                }
            )
            data = response.json()
            if 'error' in data:
                print(f"Google token exchange failed: {data}")
            return data
        except Exception as e:
            print(f"Google token exchange error: {e}")
            return None

    @staticmethod
    def verify_token(credential: str) -> Optional[Dict[str, Any]]:
        try:
            return id_token.verify_oauth2_token(
                credential,
                google_requests.Request(),
                settings.GOOGLE_CLIENT_ID
            )
        except Exception as e:
            print(f"Google token verification error: {e}")
            return None

    @staticmethod
    def fetch_ga4_traffic(property_id: str, access_token: Optional[str] = None) -> List[Dict[str, Any]]:
        if not property_id:
            return []

        try:
            if access_token:
                credentials = Credentials(token=access_token)
                client = BetaAnalyticsDataClient(credentials=credentials)
            else:
                client = BetaAnalyticsDataClient()

            request = RunReportRequest(
                property=f"properties/{property_id}",
                dimensions=[Dimension(name="date")],
                metrics=[Metric(name="activeUsers")],
                date_ranges=[DateRange(start_date="30daysAgo", end_date="today")],
            )
            
            response = client.run_report(request)
            return [
                {
                    "date": row.dimension_values[0].value,
                    "users": int(row.metric_values[0].value)  
                }
                for row in response.rows
            ]
        except Exception as e:
            print(f"GA4 API Error: {e}")
            return []
