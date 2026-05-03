import os
import json
import google.generativeai as genai
from typing import Dict, Any, List

class AIAnalyzerService:
    @staticmethod
    def analyze_seo(html_content: str, pagespeed_issues: Dict[str, Any]) -> Dict[str, Any]:
        try:
            genai.configure(api_key=os.getenv("GEMINI_API_KEY"))
            model = genai.GenerativeModel('gemini-3-flash-preview')

            prompt = f"""
            You are an elite Technical SEO Architect and Senior Frontend Developer. 
            Your objective is to comprehensively analyze the provided Google PageSpeed Insights data and raw HTML, and identify ALL actionable SEO and performance issues.

            INPUT DATA:
            - PageSpeed Failed Audits: {json.dumps(pagespeed_issues)}
            - Raw HTML (Truncated to 50k chars): {html_content[:50000]}

            TASKS:
            1. Calculate an AUTHENTIC "content_score" from 1 to 100.
            2. Identify critical and moderate issues that can be resolved via code. Provide specific code snippets.

            REQUIREMENTS:
            - Return ONLY valid JSON.
            
            Structure:
            {{
                "content_score": 85,
                "seo_fixes": [
                    {{
                        "title": "...",
                        "explanation": "...",
                        "code_fix": "..." 
                    }}
                ]
            }}
            """
            
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
