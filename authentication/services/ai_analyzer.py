import os
import json
import google.generativeai as genai
from typing import Dict, Any, List
from pydantic import BaseModel, Field

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

class AIAnalyzerService:
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
