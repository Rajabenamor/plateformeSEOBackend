import uuid
import requests
import base64
import os
from django.conf import settings
from typing import Dict, Any, Optional, Tuple
from urllib.parse import urlparse

class GitHubService:
    @staticmethod
    def exchange_token(code: str) -> Optional[str]:
        try:
            response = requests.post(
                'https://github.com/login/oauth/access_token',
                headers={'Accept': 'application/json'},
                data={
                    'client_id': settings.GITHUB_CLIENT_ID,
                    'client_secret': settings.GITHUB_CLIENT_SECRET,
                    'code': code,
                }
            )
            github_data = response.json()
            return github_data.get('access_token')
        except Exception as e:
            print(f"GitHub token exchange error: {e}")
            return None

    @staticmethod
    def get_file_content_from_url(github_token: str, target_repo: str, url: str) -> Tuple[Optional[str], Optional[str]]:
        """Maps a URL to a likely Next.js file path and fetches its content."""
        headers = {
            "Authorization": f"token {github_token}",
            "Accept": "application/vnd.github.v3+json"
        }
        
        parsed_url = urlparse(url)
        path = parsed_url.path.strip("/")
        
        # Attempt to map to Next.js App Router structure
        possible_paths = []
        if not path:
            possible_paths = ["src/app/page.tsx", "app/page.tsx", "pages/index.tsx"]
        else:
            possible_paths = [
                f"src/app/{path}/page.tsx",
                f"app/{path}/page.tsx",
                f"src/app/{path}/layout.tsx",
                f"app/{path}/layout.tsx",
                f"pages/{path}.tsx",
                f"pages/{path}/index.tsx"
            ]
            
        repo_res = requests.get(f"https://api.github.com/repos/{target_repo}", headers=headers)
        if repo_res.status_code != 200:
            return None, None
            
        default_branch = repo_res.json().get("default_branch", "main")
        
        for file_path in possible_paths:
            file_url = f"https://api.github.com/repos/{target_repo}/contents/{file_path}?ref={default_branch}"
            file_res = requests.get(file_url, headers=headers)
            if file_res.status_code == 200:
                file_data = file_res.json()
                content = base64.b64decode(file_data['content']).decode('utf-8')
                return content, file_path
                
        return None, None

    @staticmethod
    def create_pull_request(
        github_token: str,
        target_repo: str,
        fix_title: str,
        fix_explanation: str,
        target_file_path: str,
        current_code: str = None,
        suggested_code: str = None,
        code_fix: str = None
    ) -> Dict[str, Any]:
        try:
            # Use code_fix if suggested_code is not provided
            suggested_code = suggested_code or code_fix
            headers = {
                "Authorization": f"token {github_token}",
                "Accept": "application/vnd.github.v3+json"
            }

            print(f"DEBUG [GitHubService]: Creating PR for {target_repo} - File: {target_file_path}")

            # 1. Get repo info and default branch
            repo_res = requests.get(f"https://api.github.com/repos/{target_repo}", headers=headers)
            if repo_res.status_code != 200:
                err_msg = repo_res.json().get('message', 'Unknown error')
                print(f"ERROR [GitHubService]: Repo access failed: {err_msg}")
                return {"success": False, "error": f"Could not access repo: {err_msg}"}
            
            default_branch = repo_res.json().get("default_branch", "main")

            # 2. Get latest SHA from default branch
            ref_url = f"https://api.github.com/repos/{target_repo}/git/refs/heads/{default_branch}"
            ref_res = requests.get(ref_url, headers=headers)
            if ref_res.status_code != 200:
                err_msg = ref_res.json().get('message', 'Unknown error')
                return {"success": False, "error": f"Could not find branch: {err_msg}"}
            
            latest_sha = ref_res.json()['object']['sha']

            # 3. Get target file content
            file_url = f"https://api.github.com/repos/{target_repo}/contents/{target_file_path}?ref={default_branch}"
            file_res = requests.get(file_url, headers=headers)
            if file_res.status_code != 200:
                return {"success": False, "error": f"Could not find {target_file_path} in the repository. Please verify the file path."}

            file_data = file_res.json()
            file_sha = file_data['sha']
            raw_source_code = base64.b64decode(file_data['content']).decode('utf-8')

            # 4. Generate AI fix OR Use string replacement
            if current_code and suggested_code:
                print("DEBUG [GitHubService]: Performing direct string replacement.")
                if current_code not in raw_source_code:
                    return {"success": False, "error": "The specified code snippet was not found in the target file. The file may have been updated."}
                fixed_code = raw_source_code.replace(current_code, suggested_code, 1)
            else:
                print("DEBUG [GitHubService]: No direct codes provided, triggering AI fix generation.")
                fixed_code, ai_error = GitHubService._generate_ai_fix(fix_title, fix_explanation, target_file_path, raw_source_code, suggested_code)
                if ai_error:
                    return {"success": False, "error": ai_error}
                
            if not fixed_code:
                 return {"success": False, "error": "The AI failed to generate a valid fix for this code. Please try again or provide manual snippets."}

            # 5. Create new branch
            random_id = uuid.uuid4().hex[:6]
            new_branch_name = f"strive-seo-fix-{random_id}"
            branch_res = requests.post(
                f"https://api.github.com/repos/{target_repo}/git/refs",
                headers=headers,
                json={"ref": f"refs/heads/{new_branch_name}", "sha": latest_sha}
            )
            if branch_res.status_code != 201:
                return {"success": False, "error": f"Failed to create branch: {branch_res.json().get('message')}"}

            # 6. Commit changes
            encoded_code = base64.b64encode(fixed_code.encode('utf-8')).decode('utf-8')
            commit_data = {
                "message": f"Strive AI SEO Fix: {fix_title}",
                "content": encoded_code,
                "branch": new_branch_name,
                "sha": file_sha
            }
            commit_res = requests.put(
                f"https://api.github.com/repos/{target_repo}/contents/{target_file_path}",
                headers=headers,
                json=commit_data
            )
            if commit_res.status_code not in [200, 201]:
                return {"success": False, "error": f"Commit failed: {commit_res.json().get('message')}"}

            # 7. Create Pull Request
            pr_data = {
                "title": f"🚀 Strive SEO Auto-Fix: {fix_title}",
                "body": f"This PR was generated automatically by Strive AI.\n\n**File modified:** `{target_file_path}`\n\nThe AI applied optimizations for: {fix_explanation}",
                "head": new_branch_name,
                "base": default_branch
            }
            pr_res = requests.post(f"https://api.github.com/repos/{target_repo}/pulls", headers=headers, json=pr_data)
            
            if pr_res.status_code == 201:
                return {"success": True, "pr_url": pr_res.json().get("html_url")}
            
            return {"success": False, "error": f"Failed to open PR: {pr_res.json().get('message')}"}

        except Exception as e:
            print(f"CRITICAL ERROR [GitHubService]: {e}")
            return {"success": False, "error": str(e)}

    @staticmethod
    def _generate_ai_fix(title: str, explanation: str, file_path: str, source_code: str, suggested_code: str = None) -> Tuple[Optional[str], Optional[str]]:
        # Legacy fallback
        import google.generativeai as genai
        from google.generativeai.types import HarmCategory, HarmBlockThreshold
        import re
        from django.conf import settings

        try:
            api_key = os.environ.get('GEMINI_API_KEY') or getattr(settings, 'GEMINI_API_KEY', None)
            if not api_key:
                print("ERROR [_generate_ai_fix]: GEMINI_API_KEY is missing!")
                return None, "System configuration error: Missing AI API key."

            # Strip whitespace to prevent 400 errors from trailing spaces
            genai.configure(api_key=api_key.strip())
            
            # Use specific model name
            model = genai.GenerativeModel('gemini-2.5-flash')
            
            snippet_context = f"\n\nHere is a suggested code snippet to help you fix it:\n```tsx\n{suggested_code}\n```" if suggested_code else ""

            prompt = f"""
            You are an expert Next.js/React developer.
            I need to fix the following SEO issue in the code:
            Issue: {title}
            Details: {explanation}{snippet_context}

            Here is the EXACT source code of `{file_path}`:
            ```tsx
            {source_code}
            ```

            Rewrite the file to fix the SEO issue. 
            CRITICAL: Return ONLY the raw, updated code. Do NOT include markdown blocks. Do NOT include text explanations.
            """
            
            print(f"DEBUG [_generate_ai_fix]: Requesting fix from Gemini for {file_path}...")
            
            # BLOCK_ONLY_HIGH is safer for 400 errors than BLOCK_NONE on free tier keys
            safety_settings = {
                HarmCategory.HARM_CATEGORY_HATE_SPEECH: HarmBlockThreshold.BLOCK_ONLY_HIGH,
                HarmCategory.HARM_CATEGORY_HARASSMENT: HarmBlockThreshold.BLOCK_ONLY_HIGH,
                HarmCategory.HARM_CATEGORY_SEXUALLY_EXPLICIT: HarmBlockThreshold.BLOCK_ONLY_HIGH,
                HarmCategory.HARM_CATEGORY_DANGEROUS_CONTENT: HarmBlockThreshold.BLOCK_ONLY_HIGH,
            }

            response = model.generate_content(prompt, safety_settings=safety_settings)
            
            # Check if response was blocked
            if not response.candidates or response.candidates[0].finish_reason != 1:
                 reason = response.candidates[0].finish_reason if response.candidates else "Unknown"
                 print(f"ERROR [_generate_ai_fix]: AI Generation blocked. Reason: {reason}")
                 return None, f"AI generation blocked (Code: {reason}). Try a different recommendation."

            fixed_code = response.text.strip()
            print(f"DEBUG [_generate_ai_fix]: Raw AI response received ({len(fixed_code)} bytes).")
            
            # Robust extraction: find code within markdown blocks if present
            code_block_match = re.search(r'```(?:\w+)?\n?(.*?)```', fixed_code, re.DOTALL)
            if code_block_match:
                fixed_code = code_block_match.group(1).strip()
            elif fixed_code.startswith("```"):
                # Fallback for broken blocks
                fixed_code = "\n".join(fixed_code.split("\n")[1:-1])
            
            # Final sanity check
            if len(fixed_code) < 10:
                print(f"ERROR [_generate_ai_fix]: Extracted code is too short.")
                return None, "AI Generation Error: The generated code was invalid or incomplete."

            return fixed_code, None
        except Exception as e:
            print(f"AI fix generation error: {e}")
            # If 400 persists, it might be the safety_settings themselves. Try one last time without them.
            if "400" in str(e):
                 return GitHubService._generate_ai_fix_no_safety(title, explanation, file_path, source_code)
            return None, f"AI Exception: {str(e)}"

    @staticmethod
    def _generate_ai_fix_no_safety(title: str, explanation: str, file_path: str, source_code: str, suggested_code: str = None) -> Tuple[Optional[str], Optional[str]]:
        """Last resort retry without custom safety settings to avoid 400 errors."""
        import google.generativeai as genai
        import re
        from django.conf import settings
        try:
            api_key = (os.environ.get('GEMINI_API_KEY') or getattr(settings, 'GEMINI_API_KEY', None)).strip()
            genai.configure(api_key=api_key)
            model = genai.GenerativeModel('gemini-2.5-flash')
            snippet_context = f"\n\nHere is a suggested code snippet to help you fix it:\n```tsx\n{suggested_code}\n```" if suggested_code else ""
            prompt = f"Fix SEO issue '{title}' ({explanation}){snippet_context} in this file:\n{source_code}\n\nReturn ONLY the fixed code."
            response = model.generate_content(prompt)
            if not response.text: return None, "AI blocked."
            fixed_code = response.text.strip()
            code_block_match = re.search(r'```(?:\w+)?\n?(.*?)```', fixed_code, re.DOTALL)
            if code_block_match: fixed_code = code_block_match.group(1).strip()
            return fixed_code, None
        except Exception as e:
            return None, f"AI Retry Exception: {str(e)}"
