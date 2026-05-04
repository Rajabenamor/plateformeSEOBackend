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
    def __init__(self):
        # Initialize API clients
        self.ga4_service = GA4Service()
        self.pagespeed_service = PageSpeedService()
        self.gemini_service = GeminiService()
        self.scraper_service = ScraperService()

    def build_payload(self, target_url: str) -> dict:
        """
        Main orchestration method to build the final Pydantic payload with REAL intelligence.
        Uses parallel execution and caching to minimize latency and prevent timeouts.
        """
        # Check cache first
        now = time.time()
        if target_url in _ANALYSIS_CACHE:
            cached_data, timestamp = _ANALYSIS_CACHE[target_url]
            if now - timestamp < _CACHE_TTL:
                print(f"DEBUG: Returning cached payload for {target_url}")
                return cached_data

        # 1. Fetch real data from APIs in parallel
        with ThreadPoolExecutor(max_workers=3) as executor:
            future_ga4 = executor.submit(self.ga4_service.get_traffic_last_30_days)
            future_pagespeed = executor.submit(self.pagespeed_service.fetch_data, target_url)
            future_html = executor.submit(self.scraper_service.fetch_html_with_zyte, target_url)

            real_traffic_data = future_ga4.result()
            pagespeed_data = future_pagespeed.result()
            raw_html = future_html.result()

        # 2. Use Neural Engine to analyze raw data for intelligence insights
        # and generate dynamic action items in parallel
        with ThreadPoolExecutor(max_workers=2) as executor:
            future_intelligence = executor.submit(
                AIAnalyzerService.analyze_intelligence,
                traffic_data=real_traffic_data,
                pagespeed_data=pagespeed_data
            )

            # Pass the HTML content to Gemini for structural analysis
            future_action_items = executor.submit(
                self.gemini_service.generate_action_items,
                target_url, 
                pagespeed_data,
                raw_html=raw_html
            )

            intelligence = future_intelligence.result()
            dynamic_action_items = future_action_items.result()

        # 3. Construct the payload using REAL data only
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

        # 4. Validate and construct the final payload
        payload = DashboardIntelligencePayload(**payload_data)
        result = payload.model_dump()
        
        # Save to cache
        _ANALYSIS_CACHE[target_url] = (result, now)
        
        return result

