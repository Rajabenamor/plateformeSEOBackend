import json
from .schemas import DashboardIntelligencePayload
from .integrations.ga4 import GA4Service
from .integrations.pagespeed import PageSpeedService
from authentication.services.ai_analyzer import AIAnalyzerService

class DashboardAggregatorService:
    def __init__(self):
        # Initialize API clients
        self.ga4_service = GA4Service()
        self.pagespeed_service = PageSpeedService()

    def build_payload(self, target_url: str) -> dict:
        """
        Main orchestration method to build the final Pydantic payload with REAL intelligence.
        """
        # 1. Fetch real data from APIs
        real_traffic_data = self.ga4_service.get_traffic_last_30_days()
        pagespeed_data = self.pagespeed_service.fetch_data(target_url)
        
        # 2. Use Neural Engine to analyze raw data for intelligence insights
        intelligence = AIAnalyzerService.analyze_intelligence(
            traffic_data=real_traffic_data,
            pagespeed_data=pagespeed_data
        )

        # 3. Use PageSpeed dynamic action items (keeping this for now as it's already integrated)
        # We'll use the legacy GeminiService logic but wrap it in the new intelligence structure
        from .integrations.gemini import GeminiService
        gemini_service = GeminiService()
        dynamic_action_items = gemini_service.generate_action_items(target_url, pagespeed_data)

        # 4. Construct the payload using REAL data only
        payload_data = {
            "global_health_score": intelligence.get("global_health_score", 50),
            "technical_health": pagespeed_data["technical_health"] if pagespeed_data else 0,
            "traffic_velocity": intelligence.get("traffic_velocity", "flat"),
            "traffic": real_traffic_data, 
            "enriched_statistics": {
                "traffic_decay": intelligence.get("traffic_decay", []),
                "cannibalization": intelligence.get("cannibalization", []),
                "missed_clicks": intelligence.get("missed_clicks", []),
                "mobile_penalty": pagespeed_data["mobile_penalty"] if pagespeed_data else {
                    "desktop_score": 0,
                    "mobile_score": 0,
                    "penalty_gap": 0,
                    "critical_issues": ["No performance data available"]
                },
                "competitor_blind_spots": intelligence.get("competitor_blind_spots", [])
            },
            "critical_action_items": dynamic_action_items
        }
        
        # 5. Validate and construct the final payload
        payload = DashboardIntelligencePayload(**payload_data)
        return payload.model_dump()
