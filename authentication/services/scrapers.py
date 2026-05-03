import os
import requests
from urllib.parse import urlparse
from typing import Dict, Any, Optional

class ScraperService:
    @staticmethod
    def fetch_pagespeed_data(target_url: str) -> Dict[str, Any]:
        if not target_url.startswith(('http://', 'https://')):
            target_url = f"https://{target_url}"
        
        api_key = os.getenv("PAGESPEED_API_KEY")
        api_url = f"https://www.googleapis.com/pagespeedonline/v5/runPagespeed?url={target_url}&strategy=mobile&key={api_key}"
        
        try:
            response = requests.get(api_url)
            if response.status_code != 200:
                return {"score": 0, "issues": {}}

            data = response.json()
            lighthouse = data.get('lighthouseResult', {})
            performance = lighthouse.get('categories', {}).get('performance', {})
            
            raw_score = performance.get('score')
            score = int(raw_score * 100) if raw_score is not None else 0
            
            audits = lighthouse.get('audits', {})
            failed_audits = {k: v for k, v in audits.items() if v.get('score') is not None and v.get('score') < 1}
            
            return {"score": score, "issues": failed_audits}
        except Exception as e:
            print(f"PageSpeed error: {e}")
            return {"score": 0, "issues": {}}

    @staticmethod
    def fetch_html_with_zyte(url: str) -> str:
        zyte_api_key = os.getenv("ZYTE_API_KEY")
        api_url = "https://api.zyte.com/v1/extract"
        payload = {"url": url, "browserHtml": True, "geolocation": "US"}
        
        try:
            response = requests.post(api_url, auth=(zyte_api_key, ""), json=payload)
            if response.status_code == 200:
                return response.json().get("browserHtml", "")
            return ""
        except Exception as e:
            print(f"Zyte error: {e}")
            return ""

    @staticmethod
    def fetch_backlink_strength(url: str) -> int:
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
                    if data['response'][0].get('status_code') == 404:
                        return 10 
                    raw_score = data['response'][0]['page_rank_decimal']
                    if raw_score is None or raw_score == "":
                        return 10 
                    return int(float(raw_score) * 10)
                except (IndexError, KeyError):
                    return 15
            return 20
        except Exception as e:
            print(f"PageRank error: {e}")
            return 0
