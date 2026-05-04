import os
import requests
from concurrent.futures import ThreadPoolExecutor

class PageSpeedService:
    """
    Service to fetch real performance data from the Google PageSpeed Insights API.
    """
    def __init__(self):
        self.api_key = os.environ.get("PAGESPEED_API_KEY")
        self.base_url = "https://www.googleapis.com/pagespeedonline/v5/runPagespeed"

    def fetch_data(self, target_url: str) -> dict:
        """
        Fetches both Desktop and Mobile scores and extracts critical metrics.
        Returns a dictionary with parsed scores and issues.
        """
        if not self.api_key:
            print("WARNING: PAGESPEED_API_KEY is not set. Falling back to mock data.")
            return None

        # Fetch Mobile and Desktop in parallel
        with ThreadPoolExecutor(max_workers=2) as executor:
            future_mobile = executor.submit(self._fetch_strategy, target_url, "mobile")
            future_desktop = executor.submit(self._fetch_strategy, target_url, "desktop")
            
            mobile_data = future_mobile.result()
            desktop_data = future_desktop.result()

        if not mobile_data or not desktop_data:
             return None

        # Calculate scores (0-100)
        desktop_score = int(desktop_data.get('lighthouseResult', {}).get('categories', {}).get('performance', {}).get('score', 0) * 100)
        mobile_score = int(mobile_data.get('lighthouseResult', {}).get('categories', {}).get('performance', {}).get('score', 0) * 100)

        # Extract issues from mobile (e.g. LCP, render-blocking)
        audits = mobile_data.get('lighthouseResult', {}).get('audits', {})
        critical_issues = []
        
        lcp = audits.get('largest-contentful-paint', {})
        if lcp.get('score', 1) < 0.9:
            critical_issues.append(f"LCP is {lcp.get('displayValue', 'slow')}")
            
        render_blocking = audits.get('render-blocking-resources', {})
        if render_blocking.get('score', 1) < 0.9:
            critical_issues.append("Render-blocking resources found")

        # Global score approximation (weighted towards mobile)
        global_score = int((mobile_score * 0.7) + (desktop_score * 0.3))

        return {
            "global_health_score": global_score,
            "technical_health": desktop_score, # Proxying technical health as desktop performance for now
            "mobile_penalty": {
                "desktop_score": desktop_score,
                "mobile_score": mobile_score,
                "penalty_gap": max(0, desktop_score - mobile_score),
                "critical_issues": critical_issues if critical_issues else ["No critical mobile issues detected"]
            }
        }

    def _fetch_strategy(self, url: str, strategy: str) -> dict:
        try:
            params = {
                "url": url,
                "key": self.api_key,
                "strategy": strategy.upper(),
                "category": ["performance", "seo"]
            }
            response = requests.get(self.base_url, params=params, timeout=20)
            if response.ok:
                return response.json()
            else:
                print(f"PageSpeed API Error ({strategy}): {response.text}")
                return None
        except Exception as e:
            print(f"Exception fetching PageSpeed ({strategy}): {e}")
            return None
