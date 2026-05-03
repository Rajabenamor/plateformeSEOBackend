import os
import datetime
from google.analytics.data_v1beta import BetaAnalyticsDataClient
from google.analytics.data_v1beta.types import (
    DateRange,
    Dimension,
    Metric,
    RunReportRequest,
)

class GA4Service:
    """
    Service to interact with the Google Analytics 4 API.
    Uses the credentials file specified in GOOGLE_APPLICATION_CREDENTIALS.
    """
    
    def __init__(self):
        # We assume the environment variable GOOGLE_APPLICATION_CREDENTIALS 
        # is already loaded by django-environ or similar in settings.py
        self.property_id = os.environ.get("GA4_PROPERTY_ID")
        
        if not self.property_id:
            print("WARNING: GA4_PROPERTY_ID is not set. Real GA4 data will fail.")
            
        try:
            self.client = BetaAnalyticsDataClient()
        except Exception as e:
            print(f"Failed to initialize GA4 Client. Ensure credentials JSON is valid. Error: {e}")
            self.client = None

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
        (A simplified version of 'Traffic Decay Alert')
        """
        if not self.client or not self.property_id:
            return []
            
        # To accurately find decaying content, we'd compare two date ranges
        # For simplicity in this demo, let's just look at top pages last 30 days
        # In a full implementation, we would run two reports (30-60 days ago vs 0-30 days ago)
        # and calculate the delta per URL.
        
        # For now, returning an empty list so the mock aggregator falls back to generating a fake one
        # or we could implement the full complex query. Let's return empty to keep the example focused.
        return []
