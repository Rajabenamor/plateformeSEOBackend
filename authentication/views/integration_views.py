from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from django.utils import timezone
from datetime import timedelta
from django.conf import settings

from ..models import UserIntegration
from ..services.github_service import GitHubService
from ..services.google_service import GoogleService
# Import get_domain from wherever you stored it (assuming analysis.views based on standard structure)
from analysis.views import get_domain 

class IntegrationStatusView(APIView):
    permission_classes = [IsAuthenticated]
    
    def get(self, request):
        # 1. THE FIX: Safely check if the integration profile exists using hasattr
        if hasattr(request.user, 'integrations'):
            integrations = request.user.integrations
            return Response({
                "github_connected": bool(integrations.github_access_token),
                "github_repo": integrations.github_repo_linked, 
                "ga4_connected": bool(integrations.ga4_access_token),
                # 2. THE FIX: Removed getattr(settings) so the UI shows the input box!
                "ga4_property": integrations.ga4_property_id, 
                "primary_domain": integrations.primary_domain,
            })
        else:
            # If the user has no integrations connected yet, return clean nulls
            return Response({
                "github_connected": False, 
                "github_repo": None,
                "ga4_connected": False, 
                "ga4_property": None,
                "primary_domain": None
            })

class GA4ExchangeView(APIView):
    permission_classes = [IsAuthenticated]
    def post(self, request):
        code = request.data.get('code')
        if not code:
            return Response({"error": "No code provided."}, status=status.HTTP_400_BAD_REQUEST)

        token_data = GoogleService.exchange_auth_code(code)
        if not token_data or 'access_token' not in token_data:
            return Response({"error": "Google denied token exchange.", "details": token_data}, status=status.HTTP_400_BAD_REQUEST)

        integration, _ = UserIntegration.objects.get_or_create(user=request.user)
        integration.ga4_access_token = token_data.get('access_token')
        integration.ga4_refresh_token = token_data.get('refresh_token')
        
        expires_in = token_data.get('expires_in', 3600)
        integration.ga4_token_expiry = timezone.now() + timedelta(seconds=expires_in)
        integration.save()

        return Response({"message": "Google Analytics connected!"})

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
        code_fix = request.data.get('code_fix')

        try:
            integration = request.user.integrations
            if not integration.github_access_token or not integration.github_repo_linked:
                return Response({"error": "GitHub not connected."}, status=status.HTTP_403_FORBIDDEN)

            result = GitHubService.create_pull_request(
                integration.github_access_token,
                integration.github_repo_linked,
                fix_title, fix_explanation, target_file,
                current_code, suggested_code, code_fix
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
            
            # Use the imported get_domain to lock domain correctly
            url = request.data.get('url')
            if url:
                integration.primary_domain = get_domain(url)
                
            integration.save()
            return Response({"message": "Repo saved!"})
        except UserIntegration.DoesNotExist:
            return Response({"error": "GitHub not connected."}, status=status.HTTP_400_BAD_REQUEST)

class SaveGA4PropertyView(APIView):
    permission_classes = [IsAuthenticated]
    
    def post(self, request):
        property_id = request.data.get('property_id')
        if not property_id:
            return Response({"error": "Property ID required."}, status=status.HTTP_400_BAD_REQUEST)
        
        try:
            integration = request.user.integrations
            
            # 1. Update and save the ID FIRST
            integration.ga4_property_id = property_id.strip()
            url = request.data.get('url')
            if url:
                integration.primary_domain = get_domain(url)
            integration.save()
            
            # 2. TEST CONNECTION (Optional: Catch errors but don't delete the saved ID)
            try:
                from google.analytics.data_v1beta import BetaAnalyticsDataClient
                from google.analytics.data_v1beta import DateRange, Dimension, Metric, RunReportRequest
                from google.oauth2.credentials import Credentials

                if integration.ga4_access_token:
                    credentials = Credentials(token=integration.ga4_access_token)
                    client = BetaAnalyticsDataClient(credentials=credentials)
                else:
                    client = BetaAnalyticsDataClient()
                    
                req = RunReportRequest(
                    property=f"properties/{property_id.strip()}",
                    dimensions=[Dimension(name="date")],
                    metrics=[Metric(name="activeUsers")],
                    date_ranges=[DateRange(start_date="today", end_date="today")],
                )
                client.run_report(req)
                
            except Exception as e:
                print(f"DEBUG: Connection test failed: {str(e)}")
                # We return a message that it saved, but warn the user the connection test failed
                return Response({
                    "message": "Property ID saved, but connection test failed.",
                    "warning": "Check your GA4 permissions or service account."
                }, status=status.HTTP_200_OK)

            return Response({"message": "GA4 Property saved and verified!"})

        except UserIntegration.DoesNotExist:
            return Response({"error": "Google Analytics not connected."}, status=status.HTTP_400_BAD_REQUEST)

class DisconnectIntegrationView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        provider = request.data.get('provider')
        
        try:
            integration = request.user.integrations
            
            if provider == 'google':
                integration.ga4_access_token = None
                integration.ga4_refresh_token = None
                integration.ga4_property_id = None 
            elif provider == 'github':
                integration.github_access_token = None
                integration.github_repo_linked = None 
            else:
                return Response({"error": "Invalid provider."}, status=status.HTTP_400_BAD_REQUEST)

            # --- THE FIX: Wipe the primary_domain if everything is disconnected ---
            has_ga4 = bool(integration.ga4_property_id or integration.ga4_access_token)
            has_github = bool(integration.github_repo_linked or integration.github_access_token)
            
            if not has_ga4 and not has_github:
                integration.primary_domain = None
            # ----------------------------------------------------------------------

            integration.save()
            return Response({"message": f"{provider.capitalize()} disconnected successfully."}, status=status.HTTP_200_OK)
            
        except UserIntegration.DoesNotExist:
            return Response({"error": "No integrations found for this user."}, status=status.HTTP_404_NOT_FOUND)

class ResetDomainLockView(APIView):
    permission_classes = [IsAuthenticated]
    
    def post(self, request):
        try:
            integration = request.user.integrations
            integration.primary_domain = None
            integration.save()
            return Response({"message": "Domain lock cleared! Analyzed site reset."}, status=status.HTTP_200_OK)
        except UserIntegration.DoesNotExist:
            return Response({"error": "No integrations found."}, status=status.HTTP_404_NOT_FOUND)