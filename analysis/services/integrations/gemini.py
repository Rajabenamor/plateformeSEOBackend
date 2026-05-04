import os
import json
import google.generativeai as genai
import uuid
import hashlib

class GeminiService:
    """
    Service to interact with the Gemini AI model to generate SEO insights and Action Items.
    """
    
    SYSTEM_PROMPT = """
    You are an Elite Technical SEO Architect and Senior Full-Stack Engineer. Your objective is to provide high-impact, sophisticated SEO transformations that go beyond basic meta tags.

    You will be provided with raw data about a target URL, including PageSpeed Insights, Accessibility metrics, and semantic structure.

    Your task is to analyze this data and identify "Deep Fixes" – changes that significantly move the needle on both search visibility and user experience. 

    EXPANDED SCOPE OF ALLOWED CHANGES:
    1. ADVANCED METADATA: Open Graph (og:), Twitter Cards, and theme-color optimizations for mobile branding.
    2. SEMANTIC ARCHITECTURE: Rethinking <h1>-<h6> hierarchy, implementing <main>, <article>, and <aside> for better document outlining.
    3. HIGH-PERFORMANCE TAGS: Injecting `fetchpriority="high"` for LCP images, `decoding="async"` for non-critical images, and resource hints (<link rel="preconnect">).
    4. RICH SCHEMAS: Implementing complex JSON-LD (FAQPage, SoftwareApplication, Organization with SameAs, BreadcrumbList) tailored to the page content.
    5. INTERACTIVE ACCESSIBILITY: Fixing aria-labels on buttons and decorative vs. informative image handling.

    PROMPT RULES:
    - NO BULLSHIT: Avoid generic advice like "Add a meta description." Instead, suggest a high-converting, keyword-rich description based on the page context.
    - SURGICAL CODE: Every `code_fix` MUST be a literal, ready-to-paste code snippet. 
    - STRATEGIC VALUE: Explain the "Why" in terms of "Top-of-Funnel Traffic" or "Indexing Efficiency."
    - EXACT PATHS: Infer the React/Next.js file path (e.g., `src/app/page.tsx` for home, `src/app/blog/[slug]/page.tsx` for dynamic routes).

    OUTPUT FORMAT:
    Return a raw JSON object (no markdown) with an `action_items` array:
    {
      "action_items": [
        {
          "id": "uuid",
          "title": "Provocative, high-signal title",
          "impact_score": 1-10,
          "effort_level": "Low/Medium/High",
          "explanation": "Deep strategic rationale.",
          "technical_details": "Exact implementation details.",
          "code_fix": "LITERAL_CODE_SNIPPET",
          "target_file": "path/to/file.tsx"
        }
      ]
    }
    """

    def __init__(self):
        self.api_key = os.environ.get("GEMINI_API_KEY")
        if not self.api_key:
            print("WARNING: GEMINI_API_KEY is not set. Falling back to mock recommendations.")
        else:
            genai.configure(api_key=self.api_key)
            self.model = genai.GenerativeModel('gemini-1.5-pro') # Upgraded to Pro for deeper reasoning

    def generate_action_items(self, target_url: str, pagespeed_data: dict, raw_html: str = None) -> list[dict]:
        """
        Uses Gemini to generate dynamic action items based on the provided URL, performance data, and HTML structure.
        """
        if not self.api_key:
            return self._get_mock_items(target_url)

        try:
            # Construct the user prompt with the real data
            user_prompt = f"""
            Analyze the following URL, performance data, and HTML structure to generate 2 highly specific, safe code-fix recommendations.

            Target URL: {target_url}

            Performance Data context:
            {json.dumps(pagespeed_data, indent=2)}

            HTML Structure (Trimmmed for context):
            {raw_html[:10000] if raw_html else "No HTML data available"}

            Generate 2 JSON action items strictly adhering to the SYSTEM PROMPT rules. Do not include markdown blocks like ```json in the output. Return only the raw JSON string.
            """

            response = self.model.generate_content(
                contents=[
                    {"role": "user", "parts": [{"text": self.SYSTEM_PROMPT + "\n\n" + user_prompt}]}
                ]
            )

            response_text = response.text.strip()
            
            # Clean up potential markdown formatting if Gemini included it despite instructions
            if response_text.startswith("```json"):
                response_text = response_text[7:]
            if response_text.endswith("```"):
                response_text = response_text[:-3]

            data = json.loads(response_text)
            
            # Ensure STABLE IDs based on content
            for item in data.get('action_items', []):
                # Create a stable hash from title and target_file
                seed = f"{item.get('title', '')}{item.get('target_file', '')}".encode('utf-8')
                item['id'] = hashlib.md5(seed).hexdigest()
                item['status'] = "pending"

            return data.get('action_items', self._get_mock_items(target_url))

        except Exception as e:
            print(f"Error generating action items with Gemini: {e}")
            return self._get_mock_items(target_url)

    def _get_mock_items(self, target_url: str) -> list[dict]:
        """Fallback items specifically tailored to the URL if the API fails."""
        # Simple heuristic to guess the file path based on Next.js conventions
        path = target_url.replace("https://", "").replace("http://", "").split("/", 1)
        route = path[1] if len(path) > 1 else ""
        target_file = f"src/app/{route}/page.tsx" if route else "src/app/page.tsx"
        target_file = target_file.replace("//", "/")

        return [
            {
                "id": str(uuid.uuid4()),
                "title": f"Optimize Meta Title for {target_url}",
                "impact_score": 7,
                "effort_level": "Low",
                "explanation": f"The title for {target_url} might not be optimized for click-through rate. An engaging title directly impacts traffic.",
                "technical_details": "Inject a highly optimized <title> tag.",
                "code_fix": f"<title>Optimized Page | Better CTR</title>",
                "target_file": target_file,
                "status": "pending"
            },
            {
                "id": str(uuid.uuid4()),
                "title": f"Ensure H1 Tags Exist",
                "impact_score": 6,
                "effort_level": "Low",
                "explanation": "Every page needs a clear, descriptive H1 tag to help search engines understand the core topic.",
                "technical_details": "Add an H1 tag to the top of the page structure.",
                "code_fix": f"<h1 className=\"text-3xl font-bold\">Welcome to {target_url}</h1>",
                "target_file": target_file,
                "status": "pending"
            }
        ]
