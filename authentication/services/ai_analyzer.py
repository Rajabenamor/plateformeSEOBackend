import os
import json
import google.generativeai as genai
from typing import Dict, Any, List, Optional
from pydantic import BaseModel, Field

class TrafficDecayAlert(BaseModel):
    url: str
    drop_percentage: float = Field(..., description="Percentage drop over 30 days")
    recommended_action: str

class CannibalizationWarning(BaseModel):
    keyword: str
    competing_urls: List[str]
    recommended_action: str

class MissedClicksMetric(BaseModel):
    keyword: str
    url: str
    current_position: float
    current_ctr: float
    potential_traffic_gain: int = Field(..., description="Estimated extra clicks if CTR hit industry average")

class CompetitorBlindSpot(BaseModel):
    target_keyword: str
    missing_topics: List[str]
    competitor_urls: List[str]

class FixObject(BaseModel):
    issue_type: str = Field(..., description="Category of the issue: e.g., 'Performance', 'Meta-Tag', 'Accessibility', 'Semantic-HTML'")
    severity: int = Field(..., ge=1, le=10, description="Severity of the issue (1 = Low, 10 = Critical)")
    file_path: str = Field(..., description="The exact relative file path in the repository (e.g., 'src/app/page.tsx')")
    current_code: str = Field(..., description="The EXACT, literal snippet of existing code that must be replaced. Must match the source file character-for-character.")
    suggested_code: str = Field(..., description="The exact new code snippet to inject in place of current_code.")
    explanation: str = Field(..., description="A clear, business-value explanation of why this improves SEO.")

class AIAnalysisResponse(BaseModel):
    content_score: int
    seo_fixes: list[FixObject]

class IntelligenceResponse(BaseModel):
    traffic_velocity: str = Field(..., description="'trending_up', 'trending_down', 'flat'")
    traffic_decay: List[TrafficDecayAlert]
    cannibalization: List[CannibalizationWarning]
    missed_clicks: List[MissedClicksMetric]
    competitor_blind_spots: List[CompetitorBlindSpot]
    global_health_score: int

class AIAnalyzerService:
    @staticmethod
    def analyze_intelligence(traffic_data: List[Dict], pagespeed_data: Dict) -> Dict[str, Any]:
        try:
            genai.configure(api_key=os.getenv("GEMINI_API_KEY"))
            model = genai.GenerativeModel('gemini-1.5-pro')

            prompt = f"""
            You are a Neural SEO Intelligence Engine. Your task is to analyze RAW DATA and generate REAL insights. 
            NO MOCKUPS. NO PLACEHOLDERS.

            INPUT DATA:
            - Traffic Data (GA4): {json.dumps(traffic_data)}
            - PageSpeed Data: {json.dumps(pagespeed_data)}

            TASKS:
            1. Analyze traffic trends to determine 'traffic_velocity'.
            2. Identify 'traffic_decay' by looking for specific pages with declining users.
            3. Detect potential 'cannibalization' if multiple pages appear to target similar concepts (infer from PageSpeed URLs if GSC is missing).
            4. Calculate 'missed_clicks' by estimating potential traffic gain if current performance bottlenecks (from PageSpeed) were resolved.
            5. Identify 'competitor_blind_spots' based on industry standards for the detected niche.
            6. Calculate a 'global_health_score' (0-100) combining performance and traffic stability.

            Return ONLY a JSON object matching the IntelligenceResponse schema.
            """

            response = model.generate_content(
                prompt,
                generation_config=genai.GenerationConfig(
                    response_mime_type="application/json",
                    response_schema=IntelligenceResponse
                )
            )
            return json.loads(response.text)
        except Exception as e:
            print(f"Intelligence Analysis Error: {e}")
            return {
                "traffic_velocity": "flat",
                "traffic_decay": [],
                "cannibalization": [],
                "missed_clicks": [],
                "competitor_blind_spots": [],
                "global_health_score": 50
            }

    @staticmethod
    def analyze_seo(source_code: str, file_path: str, pagespeed_issues: Dict[str, Any], ignored_issues: List[Dict[str, str]] = None) -> Dict[str, Any]:
        try:
            genai.configure(api_key=os.getenv("GEMINI_API_KEY"))
            # Using gemini-1.5-pro for better structured output adherence and reasoning
            model = genai.GenerativeModel('gemini-1.5-pro')

            ignored_context = ""
            if ignored_issues:
                ignored_context = f"\n            - Ignored Issues (DO NOT SUGGEST THESE): {json.dumps(ignored_issues)}"

            prompt = f"""
            You are an elite Principal Technical SEO Strategist and Senior React/Next.js Engineer. 
            Your objective is to analyze a website's performance data alongside its ACTUAL source code, and provide surgical, code-level SEO fixes.

            You will be provided with:
            1. PageSpeed Insights Failed Audits
            2. The raw source code of the relevant file for this URL (Target File: {file_path or 'Unknown'})
            3. [Optional] A list of previously REJECTED fixes by the user. Do NOT suggest these again.

            INPUT DATA:
            - PageSpeed Failed Audits: {json.dumps(pagespeed_issues)}{ignored_context}
            - Raw Source Code: 
            ```tsx
            {source_code[:50000]}
            ```

            CRITICAL RULES FOR CODE EXECUTION:
            1. SURGICAL PRECISION: Do not rewrite entire files. Identify the absolute minimum snippet of code (`current_code`) required to apply the fix.
            2. EXACT MATCHING: The `current_code` MUST perfectly match the provided source code, preserving exact indentation, line breaks, and whitespace. We will use `str.replace(current_code, suggested_code)` programmatically. If it doesn't match exactly, the system will crash.
            3. SAFE CHANGES ONLY: Limit suggestions to Meta tags, Semantic HTML (H1-H6 structure), Image attributes (alt/width/height), and Structured Data (JSON-LD). 
            4. DO NOT BREAK UI: Do not alter Tailwind classes, CSS layouts, or React hooks/state logic.
            5. DETERMINISTIC JSON: You must respond ONLY with a JSON object matching the provided schema.

            THINKING PROCESS:
            - Review the PageSpeed data for vulnerabilities.
            - Look at the provided source code to find the exact lines causing the vulnerability.
            - Formulate the exact replacement string.
            - Calculate an AUTHENTIC "content_score" from 1 to 100 based on the code quality.
            - Output the strict JSON.
            """
            
            response = model.generate_content(
                prompt,
                generation_config=genai.GenerationConfig(
                    response_mime_type="application/json",
                    response_schema=AIAnalysisResponse
                )
            )
            return json.loads(response.text)
        except Exception as e:
            print(f"Gemini API Error: {e}")
            return {"content_score": 0, "seo_fixes": []}
