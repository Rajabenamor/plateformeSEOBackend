from typing import Dict, Any, Optional
from .scrapers import ScraperService
from .google_service import GoogleService
from .ai_analyzer import AIAnalyzerService
from .github_service import GitHubService
from analysis.models import IgnoredRecommendation

class SEOCalculatorService:
    @staticmethod
    def calculate_metrics(url: str, user=None, ga4_property_id: Optional[str] = None, ga4_token: Optional[str] = None) -> Dict[str, Any]:
        try:
            # 1. Fetch external data
            pagespeed_data = ScraperService.fetch_pagespeed_data(url)
            technical_health = pagespeed_data.get("score", 0)
            
            traffic_data = GoogleService.fetch_ga4_traffic(ga4_property_id, ga4_token)
            backlink_strength = ScraperService.fetch_backlink_strength(url) 
            
            source_code = None
            file_path = None
            ignored_issues = []
            
            # If user has github connected, fetch source code
            if user and getattr(user, 'github_access_token', None) and getattr(user, 'github_repo_linked', None):
                github_token = user.github_access_token
                target_repo = user.github_repo_linked
                source_code, file_path = GitHubService.get_file_content_from_url(github_token, target_repo, url)
                
            if user:
                ignored_recs = IgnoredRecommendation.objects.filter(user=user)
                ignored_issues = [
                    {"issue_type": rec.issue_type, "file_path": rec.file_path} 
                    for rec in ignored_recs
                ]
                
            if not source_code:
                # Fallback to scraped HTML
                source_code = ScraperService.fetch_html_with_zyte(url)
                if source_code:
                    source_code = source_code[:50000] # Truncate large files
            
            # 2. AI Analysis
            content_score = 0
            seo_fixes = []
            
            if source_code or pagespeed_data.get("issues"):
                ai_analysis = AIAnalyzerService.analyze_seo(source_code, file_path, pagespeed_data.get("issues", {}), ignored_issues)
                content_score = ai_analysis.get("content_score", 0)
                seo_fixes = ai_analysis.get("seo_fixes", [])
            
            if not seo_fixes and content_score == 0:
                seo_fixes = [{
                    "issue_type": "Rate-Limit",
                    "severity": 1,
                    "file_path": file_path or "Unknown",
                    "current_code": "",
                    "suggested_code": "",
                    "explanation": "Our AI engine hit a rate limit. Please wait 30 seconds and try re-scanning the site."
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
