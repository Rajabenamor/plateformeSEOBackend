import os
import json
import requests
from urllib.parse import urlparse
from google.analytics.data_v1beta import BetaAnalyticsDataClient
from google.analytics.data_v1beta import DateRange, Dimension, Metric, RunReportRequest
from google.oauth2.credentials import Credentials
import google.generativeai as genai

# Configure global settings once
genai.configure(api_key=os.getenv("GEMINI_API_KEY"))

def fetch_ga4_traffic(property_id, access_token=None):
    """
    Fetches Active Users for the last 30 days from GA4.
    Updated to accept dynamic property IDs and OAuth tokens for user-linked accounts.
    """
    if not property_id:
        return []

    # If the user linked their account via OAuth, use their token. 
    # Otherwise, it falls back to the server's default credentials (for testing).
    client_options = {}
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
    
    try: 
        response = client.run_report(request)
        formatted_data = [
            {
                "date": row.dimension_values[0].value,
                "users": int(row.metric_values[0].value)  
            }
            for row in response.rows
        ]
        return formatted_data
    except Exception as e:
        print(f"GA4 API Error: {e}")
        return []

def fetch_pagespeed_data(target_url):
    """Fetches real performance data with robust error handling."""
    if not target_url.startswith(('http://', 'https://')):
        target_url = f"https://{target_url}"
    
    api_key = os.getenv("PAGESPEED_API_KEY")
    api_url = f"https://www.googleapis.com/pagespeedonline/v5/runPagespeed?url={target_url}&strategy=mobile&key={api_key}"
    
    try:
        response = requests.get(api_url)
        if response.status_code != 200:
            print(f"PageSpeed API returned status: {response.status_code}")
            return {"score": 0, "issues": {}}

        data = response.json()
        lighthouse = data.get('lighthouseResult', {})
        categories = lighthouse.get('categories', {})
        performance = categories.get('performance', {})
        
        raw_score = performance.get('score')
        score = int(raw_score * 100) if raw_score is not None else 0
        
        audits = lighthouse.get('audits', {})
        failed_audits = {k: v for k, v in audits.items() if v.get('score') is not None and v.get('score') < 1}
        
        return {
            "score": score,
            "issues": failed_audits
        }
    except Exception as e:
        print(f"CRITICAL PAGESPEED ERROR: {e}")
        return {"score": 0, "issues": {}}

def fetch_html_with_zyte(url):
    """Uses Zyte API to render JavaScript and extract the final HTML."""
    zyte_api_key = os.getenv("ZYTE_API_KEY")
    api_url = "https://api.zyte.com/v1/extract"

    payload = {
        "url": url,
        "browserHtml": True,
        "geolocation": "US",
    }
    
    try:
        response = requests.post(api_url, auth=(zyte_api_key, ""), json=payload)
        
        if response.status_code == 200:
            return response.json().get("browserHtml", "")
        elif response.status_code == 520:
            print("DEBUG: Zyte Website Ban detected.")
            return ""
        else:
            print(f"DEBUG: Zyte API Error {response.status_code}: {response.text}")
            return ""
            
    except requests.exceptions.RequestException as e:
        print(f"DEBUG: Network error connecting to Zyte: {e}")
        return ""

def analyze_seo_with_ai(html_content, pagespeed_issues):
    """Consolidated AI function using Gemini 2.5 Flash and strict JSON configuration."""
    # Use the fastest, most capable model for text tasks
    model = genai.GenerativeModel('gemini-2.5-flash')

    prompt = f"""
    You are an expert technical SEO assistant.
    Review this raw Google PageSpeed Insights failed audits list: {json.dumps(pagespeed_issues)}
    And review this raw HTML: {html_content[:50000]}
    
    1. Calculate a "content_score" from 1 to 100 based on the presence of meta tags, H1/H2 structure, and keyword density.
    2. Identify the 3 most critical issues that can be fixed with code.
    
    Return EXACTLY this JSON structure:
    {{
        "content_score": 85,
        "seo_fixes": [
            {{
                "title": "Short title of the issue",
                "explanation": "Brief explanation of why it matters",
                "code_fix": "The exact HTML/CSS/JS snippet to fix it"
            }}
        ]
    }}
    """
    try:
        # Enforce strict JSON generation natively
        response = model.generate_content(
            prompt,
            generation_config=genai.GenerationConfig(
                response_mime_type="application/json"
            )
        )
        return json.loads(response.text)
    except Exception as e:
        print(f"Gemini API Error: {e}")
        return {"content_score": 0, "seo_fixes": []}

def fetch_backlink_strength(url):
    """Fetches domain authority using the FREE Open PageRank API."""
    opr_api_key = os.getenv("OPEN_PAGERANK_API_KEY")
    if not opr_api_key:
        return 45 

    if not url.startswith(('http://', 'https://')):
        url = 'https://' + url
        
    domain = urlparse(url).netloc
    if domain.startswith('www.'):
        domain = domain[4:]

    headers = {'API-OPR': opr_api_key}
    api_url = f"https://openpagerank.com/api/v1.0/getPageRank?domains[]={domain}"

    try:
        response = requests.get(api_url, headers=headers)
        if response.status_code == 200:
            data = response.json()
            try:
                raw_score = data['response'][0]['page_rank_decimal']
                if raw_score is None:
                    return 10 
                return int(float(raw_score) * 10)
            except (IndexError, KeyError):
                return 15
        return 20
    except Exception as e:
        print(f"CRITICAL Open PageRank Error: {e}")
        return 0

def calculate_seo_metrics(url, user_ga4_property_id=None, user_oauth_token=None):
    """
    Core function that orchestrates all dynamic data fetching.
    Follows best practices by declaring defaults before the try/except block.
    """
    # 1. Initialize default state to avoid reference errors if something fails
    technical_health = 0
    content_score = 0
    backlink_strength = 0
    traffic_data = []
    seo_fixes = []

    try:
        # 2. Fetch data from external APIs
        pagespeed_data = fetch_pagespeed_data(url)
        technical_health = pagespeed_data.get("score", 0)
        
        traffic_data = fetch_ga4_traffic(user_ga4_property_id, user_oauth_token)
        backlink_strength = fetch_backlink_strength(url) 
        
        html_content = fetch_html_with_zyte(url)
        
        # 3. Process with AI
        if html_content or pagespeed_data.get("issues"):
            ai_analysis = analyze_seo_with_ai(html_content, pagespeed_data.get("issues", {}))
            content_score = ai_analysis.get("content_score", 0)
            seo_fixes = ai_analysis.get("seo_fixes", [])

        # 4. Handle Gemini Rate Limits Gracefully
        if not seo_fixes and content_score == 0:
            seo_fixes = [{
                "title": "⏳ AI Engine Cooling Down",
                "explanation": "Our AI engine hit a rate limit. Please wait 30 seconds and try re-scanning the site.",
                "code_fix": ""
            }]

    except Exception as e:
        print(f"DEBUG: Analysis failed. Reason: {e}")
        # Defaults are already set, so we don't need messy 'locals()' checks here

    # Calculate overall score
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