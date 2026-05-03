from .scrapers import ScraperService
from .google_service import GoogleService
from .ai_analyzer import AIAnalyzerService
from typing import Dict, Any, Optional

class SEOCalculatorService:
    @staticmethod
    def calculate_metrics(url: str, ga4_property_id: Optional[str] = None, ga4_token: Optional[str] = None) -> Dict[str, Any]:
        try:
            # 1. Fetch external data
            pagespeed_data = ScraperService.fetch_pagespeed_data(url)
            technical_health = pagespeed_data.get("score", 0)
            
            traffic_data = GoogleService.fetch_ga4_traffic(ga4_property_id, ga4_token)
            backlink_strength = ScraperService.fetch_backlink_strength(url) 
            
            html_content = ScraperService.fetch_html_with_zyte(url)
            
            # 2. AI Analysis
            content_score = 0
            seo_fixes = []
            
            if html_content or pagespeed_data.get("issues"):
                ai_analysis = AIAnalyzerService.analyze_seo(html_content, pagespeed_data.get("issues", {}))
                content_score = ai_analysis.get("content_score", 0)
                seo_fixes = ai_analysis.get("seo_fixes", [])
            
            if not seo_fixes and content_score == 0:
                seo_fixes = [{
                    "title": "⏳ AI Engine Cooling Down",
                    "explanation": "Our AI engine hit a rate limit. Please wait 30 seconds and try re-scanning the site.",
                    "code_fix": ""
                }]

            # 3. Final score calculation
            overall_score = int((technical_health * 0.4) + (content_score * 0.4) + (backlink_strength * 0.2))

            return {
                "analyzed_url": url,
                "overall_score": overall_score,
                "technical_health": technical_health,
                "content_score": content_score,
                "backlink_strength": backlink_strength,
                "traffic": traffic_data,
                "seo_fixes": seo_fixes,
            }

        except Exception as e:
            print(f"SEO calculation error: {e}")
            return {
                "analyzed_url": url,
                "overall_score": 0,
                "technical_health": 0,
                "content_score": 0,
                "backlink_strength": 0,
                "traffic": [],
                "seo_fixes": [],
            }
