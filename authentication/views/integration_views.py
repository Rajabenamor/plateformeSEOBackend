from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from ..models import UserIntegration
from ..services.github_service import GitHubService

class IntegrationStatusView(APIView):
    permission_classes = [IsAuthenticated]
    def get(self, request):
        try:
            integrations = request.user.integrations
            return Response({
                "github_connected": bool(integrations.github_access_token),
                "github_repo": integrations.github_repo_linked, 
                "ga4_connected": bool(integrations.ga4_access_token),
                "ga4_property": integrations.ga4_property_id
            })
        except UserIntegration.DoesNotExist:
            return Response({
                "github_connected": False, "github_repo": None,
                "ga4_connected": False, "ga4_property": None
            })

class GithubExchangeView(APIView):
    permission_classes = [IsAuthenticated]
    def post(self, request):
        code = request.data.get('code')
        installation_id = request.data.get('installation_id')
        if not code:
            return Response({"error": "No code provided."}, status=status.HTTP_400_BAD_REQUEST)

        access_token = GitHubService.exchange_token(code)
        if not access_token:
            return Response({"error": "GitHub denied token exchange."}, status=status.HTTP_400_BAD_REQUEST)

        integration, _ = UserIntegration.objects.get_or_create(user=request.user)
        integration.github_access_token = access_token
        if installation_id:
            integration.github_repo_linked = installation_id 
        integration.save()

        return Response({"message": "GitHub connected!"})

class CreateGithubPRView(APIView):
    permission_classes = [IsAuthenticated]
    def post(self, request):
        fix_title = request.data.get('title', 'SEO Fix')
        fix_explanation = request.data.get('explanation', '')
        target_file = request.data.get('target_file', 'src/app/page.tsx')
        current_code = request.data.get('current_code')
        suggested_code = request.data.get('suggested_code')

        try:
            integration = request.user.integrations
            if not integration.github_access_token or not integration.github_repo_linked:
                return Response({"error": "GitHub not connected."}, status=status.HTTP_403_FORBIDDEN)

            result = GitHubService.create_pull_request(
                integration.github_access_token,
                integration.github_repo_linked,
                fix_title, fix_explanation, target_file,
                current_code, suggested_code
            )

            if result["success"]:
                return Response({"message": "Success!", "pr_url": result["pr_url"]}, status=status.HTTP_201_CREATED)
            return Response({"error": result["error"]}, status=status.HTTP_400_BAD_REQUEST)

        except UserIntegration.DoesNotExist:
            return Response({"error": "GitHub not connected."}, status=status.HTTP_403_FORBIDDEN)
class SaveGithubRepoView(APIView):
    permission_classes = [IsAuthenticated]
    def post(self, request):
        repo_name = request.data.get('repo_name')
        if not repo_name:
            return Response({"error": "Repo name required."}, status=status.HTTP_400_BAD_REQUEST)
        try:
            integration = request.user.integrations
            integration.github_repo_linked = repo_name.strip()
            integration.save()
            return Response({"message": "Repo saved!"})
        except UserIntegration.DoesNotExist:
            return Response({"error": "GitHub not connected."}, status=status.HTTP_400_BAD_REQUEST)
