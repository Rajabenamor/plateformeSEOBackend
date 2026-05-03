import json
from .schemas import DashboardIntelligencePayload
from .integrations.ga4 import GA4Service
from .integrations.pagespeed import PageSpeedService
from .integrations.gemini import GeminiService

class DashboardAggregatorService:
    def __init__(self):
        # Initialize API clients
        self.ga4_service = GA4Service()
        self.pagespeed_service = PageSpeedService()
        self.gemini_service = GeminiService()

    def build_payload(self, target_url: str) -> dict:
        """
        Main orchestration method to build the final Pydantic payload.
        """
        # 1. Fetch real data from APIs
        real_traffic_data = self.ga4_service.get_traffic_last_30_days()
        pagespeed_data = self.pagespeed_service.fetch_data(target_url)
        
        # 2. Determine velocity based on real data (fallback to flat if no data)
        traffic_velocity = "flat"
        if real_traffic_data:
            traffic_velocity = self.ga4_service.get_traffic_velocity(real_traffic_data)

        # Use pagespeed data if available, otherwise mock
        global_score = pagespeed_data["global_health_score"] if pagespeed_data else 72
        technical_health = pagespeed_data["technical_health"] if pagespeed_data else 85
        mobile_penalty = pagespeed_data["mobile_penalty"] if pagespeed_data else {
            "desktop_score": 92,
            "mobile_score": 45,
            "penalty_gap": 47,
            "critical_issues": ["LCP is 4.5s", "Render-blocking resources"]
        }

        # 3. Use Gemini to dynamically generate Action Items based on the URL and fetched data
        dynamic_action_items = self.gemini_service.generate_action_items(target_url, pagespeed_data)

        # 4. Load the rest of the mock data while we integrate the other APIs
        payload_data = {
            "global_health_score": global_score,
            "technical_health": technical_health,
            "traffic_velocity": traffic_velocity,
            "traffic": real_traffic_data if real_traffic_data else [
                {"date": "20260401", "users": 120, "displayDate": "Apr 1"},
                {"date": "20260408", "users": 150, "displayDate": "Apr 8"},
                {"date": "20260415", "users": 180, "displayDate": "Apr 15"},
                {"date": "20260422", "users": 130, "displayDate": "Apr 22"},
                {"date": "20260429", "users": 170, "displayDate": "Apr 29"},
                {"date": "20260503", "users": 210, "displayDate": "May 3"}
            ], # Fallback to mock if API fails so the chart doesn't break
            "enriched_statistics": {
                "traffic_decay": [
                    {
                        "url": "/blog/old-seo-tips",
                        "drop_percentage": 25.5,
                        "recommended_action": "Refresh content with 2026 data"
                    }
                ],
                "cannibalization": [
                    {
                        "keyword": "seo services",
                        "competing_urls": ["/services", "/seo-services-overview"],
                        "recommended_action": "Consolidate /seo-services-overview into /services using a 301 redirect"
                    }
                ],
                "missed_clicks": [
                    {
                        "keyword": "affordable seo",
                        "url": "/pricing",
                        "current_position": 4.2,
                        "current_ctr": 0.8,
                        "potential_traffic_gain": 450
                    }
                ],
                "mobile_penalty": mobile_penalty,
                "competitor_blind_spots": [
                    {
                        "target_keyword": "enterprise seo",
                        "missing_topics": ["ROI calculation", "custom reporting"],
                        "competitor_urls": ["https://competitor.com/enterprise-seo"]
                    }
                ]
            },
            "critical_action_items": dynamic_action_items
        }
        
        # 5. Validate and construct the final payload using Pydantic
        payload = DashboardIntelligencePayload(**payload_data)
        
        # Return as a standard dictionary for Django JsonResponse
        return payload.model_dump()
