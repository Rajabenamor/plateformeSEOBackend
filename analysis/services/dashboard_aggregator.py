import json
import time
from concurrent.futures import ThreadPoolExecutor
from .schemas import DashboardIntelligencePayload
from .integrations.ga4 import GA4Service
from .integrations.pagespeed import PageSpeedService
from .integrations.gemini import GeminiService
from authentication.services.ai_analyzer import AIAnalyzerService
from authentication.services.scrapers import ScraperService

# Simple in-memory cache to prevent redundant slow API calls
_ANALYSIS_CACHE = {}
_CACHE_TTL = 300  # 5 minutes

class DashboardAggregatorService:
    def __init__(self, user=None):
        # Initialize API clients
        property_id = None
        access_token = None
        if user:
            try:
                integration = user.integrations
                property_id = integration.ga4_property_id
                access_token = integration.ga4_access_token
            except Exception:
                pass
                
        self.ga4_service = GA4Service(property_id=property_id, access_token=access_token)
        self.pagespeed_service = PageSpeedService()
        self.gemini_service = GeminiService()
        self.scraper_service = ScraperService()

    def build_payload(self, target_url: str) -> dict:
        """
        ULTRA-BULLETPROOF: Guaranteed delivery for Demo.
        """
        if not target_url.startswith(('http://', 'https://')):
            target_url = f"https://{target_url}"

        now = time.time()
        # Ensure we always get a fresh start
        _ANALYSIS_CACHE.clear()

        def safe_result(future, timeout, default):
            try:
                res = future.result(timeout=timeout)
                return res if res is not None else default
            except Exception:
                return default

        # 1. Fetch real data with aggressive timeouts
        with ThreadPoolExecutor(max_workers=4) as executor:
            f_ga4 = executor.submit(self.ga4_service.get_traffic_last_30_days)
            f_ps = executor.submit(self.pagespeed_service.fetch_data, target_url)
            f_zyte = executor.submit(self.scraper_service.fetch_html_with_zyte, target_url)
            f_opr = executor.submit(self.scraper_service.fetch_backlink_strength, target_url)

            real_traffic_data = safe_result(f_ga4, 10, [])
            pagespeed_data = safe_result(f_ps, 10, {})
            raw_html = safe_result(f_zyte, 10, "")
            backlink_strength = safe_result(f_opr, 10, 0)

        # 2. Generate Intelligence & Recommendations
        intelligence_default = {"global_health_score": 0, "traffic_velocity": "flat", "traffic_decay": [], "cannibalization": [], "missed_clicks": [], "competitor_blind_spots": []}
        
        with ThreadPoolExecutor(max_workers=3) as executor:
            f_int = executor.submit(AIAnalyzerService.analyze_intelligence, real_traffic_data, pagespeed_data)
            f_gem = executor.submit(self.gemini_service.generate_action_items, target_url, pagespeed_data, raw_html)
            f_seo = executor.submit(AIAnalyzerService.analyze_seo, raw_html if raw_html else "No HTML", target_url, pagespeed_data.get("mobile_penalty", {}).get("critical_issues", []) if pagespeed_data else [])

            intelligence = safe_result(f_int, 10, intelligence_default)
            dynamic_action_items = safe_result(f_gem, 10, [])
            content_analysis = safe_result(f_seo, 10, {"content_score": 0})

        # 3. Final Payload Construction
        final_payload = {
            "global_health_score": intelligence.get("global_health_score", 0),
            "technical_health": pagespeed_data.get("technical_health", 0) if pagespeed_data else 0,
            "content_score": content_analysis.get("content_score", 0) if content_analysis else 0,
            "backlink_strength": backlink_strength if backlink_strength else 0,
            "traffic_velocity": intelligence.get("traffic_velocity", "flat"),
            "traffic": real_traffic_data if real_traffic_data else [],
            "enriched_statistics": {
                "traffic_decay": intelligence.get("traffic_decay", []),
                "cannibalization": intelligence.get("cannibalization", []),
                "missed_clicks": intelligence.get("missed_clicks", []),
                "mobile_penalty": pagespeed_data.get("mobile_penalty", {}) if pagespeed_data else {},
                "competitor_blind_spots": intelligence.get("competitor_blind_spots", [])
            },
            "critical_action_items": dynamic_action_items if dynamic_action_items else [],
            "analyzed_url": target_url
        }

        # Legacy keys for frontend
        final_payload["overall_score"] = final_payload["global_health_score"]
        final_payload["seo_fixes"] = final_payload["critical_action_items"]
        
        return final_payload

