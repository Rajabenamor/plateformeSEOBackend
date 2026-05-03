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
        suggested_code: str = None
    ) -> Dict[str, Any]:
        try:
            headers = {
                "Authorization": f"token {github_token}",
                "Accept": "application/vnd.github.v3+json"
            }

            # 1. Get repo info and default branch
            repo_res = requests.get(f"https://api.github.com/repos/{target_repo}", headers=headers)
            if repo_res.status_code != 200:
                return {"success": False, "error": f"Could not access repo: {repo_res.json().get('message')}"}
            
            default_branch = repo_res.json().get("default_branch", "main")

            # 2. Get latest SHA from default branch
            ref_url = f"https://api.github.com/repos/{target_repo}/git/refs/heads/{default_branch}"
            ref_res = requests.get(ref_url, headers=headers)
            if ref_res.status_code != 200:
                return {"success": False, "error": f"Could not find branch: {ref_res.json().get('message')}"}
            
            latest_sha = ref_res.json()['object']['sha']

            # 3. Get target file content
            file_url = f"https://api.github.com/repos/{target_repo}/contents/{target_file_path}?ref={default_branch}"
            file_res = requests.get(file_url, headers=headers)
            if file_res.status_code != 200:
                return {"success": False, "error": f"Could not find {target_file_path} in the repository."}

            file_data = file_res.json()
            file_sha = file_data['sha']
            raw_source_code = base64.b64decode(file_data['content']).decode('utf-8')

            # 4. Generate AI fix OR Use string replacement
            if current_code and suggested_code:
                if current_code not in raw_source_code:
                    return {"success": False, "error": "The specified code snippet was not found in the target file. The file may have been updated."}
                fixed_code = raw_source_code.replace(current_code, suggested_code, 1)
            else:
                # Fallback to AI rewrite if string replacement is not provided (Legacy)
                fixed_code = GitHubService._generate_ai_fix(fix_title, fix_explanation, target_file_path, raw_source_code)
                
            if not fixed_code:
                 return {"success": False, "error": "Failed to generate or apply the fix."}

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
            print(f"GitHub service error: {e}")
            return {"success": False, "error": str(e)}

    @staticmethod
    def _generate_ai_fix(title: str, explanation: str, file_path: str, source_code: str) -> Optional[str]:
        # Legacy fallback
        import google.generativeai as genai
        try:
            genai.configure(api_key=os.environ.get('GEMINI_API_KEY'))
            model = genai.GenerativeModel('gemini-2.5-flash-lite')
            
            prompt = f"""
            You are an expert Next.js/React developer.
            I need to fix the following SEO issue in the code:
            Issue: {title}
            Details: {explanation}

            Here is the EXACT source code of `{file_path}`:
            ```
            {source_code}
            ```

            Rewrite the file to fix the SEO issue. 
            CRITICAL: Return ONLY the raw, updated code. Do NOT include markdown blocks. Do NOT include text explanations.
            """
            
            response = model.generate_content(prompt)
            fixed_code = response.text.strip()
            
            if fixed_code.startswith("```"):
                fixed_code = "\n".join(fixed_code.split("\n")[1:-1])
            
            return fixed_code
        except Exception as e:
            print(f"AI fix generation error: {e}")
            return None
