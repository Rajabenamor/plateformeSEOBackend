from django.shortcuts import render
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from rest_framework import generics
from urllib.parse import urlparse

from .serializers import AnalysisHistorySerializer
from .models import AnalysisHistory, IgnoredRecommendation
from .services.dashboard_aggregator import DashboardAggregatorService

# --- HELPERS ---
def get_domain(url):
    """Extracts the base domain from a URL (e.g., 'example.com')."""
    if not url: return None
    url = url if url.startswith(('http://', 'https://')) else f"https://{url}"
    domain = urlparse(url).netloc
    return domain.replace('www.', '').lower()

def validate_analysis_access(user, target_url):
    # If the user doesn't have an integrations profile yet, allow access
    if not hasattr(user, 'integrations'):
        return True, ""

    integrations = user.integrations
    target_domain = get_domain(target_url)
    
    has_ga4 = bool(integrations.ga4_property_id or integrations.ga4_access_token)
    has_github = bool(integrations.github_repo_linked or integrations.github_access_token)
    
    # CONDITION 1: If no integrations are linked, user can analyze any site
    if not (has_ga4 or has_github):
        return True, ""

    # CONDITION 2: Integrations exist, ensure we have a primary domain locked
    stored_domain = getattr(integrations, 'primary_domain', None)
    
    if not stored_domain:
        # THE FIX: Lock the integrations to the CURRENT site being analyzed right now,
        # instead of digging up old test sites from the user's history.
        integrations.primary_domain = target_domain
        integrations.save()
        stored_domain = target_domain

    # CONDITION 3: Block if the target doesn't match the locked domain
    if stored_domain and target_domain != get_domain(stored_domain):
        return False, f"Integration active for {stored_domain}. You cannot analyze {target_domain}.|_DOMAIN_|{stored_domain}"
        
    return True, ""


# --- VIEWS ---
class DashboardDataView(APIView):
    """
    Returns the aggregated intelligence payload for the dashboard and saves it to history.
    """
    permission_classes = [IsAuthenticated]

    def get(self, request):
        url = request.query_params.get('url')
        if not url:
            return Response({"error": "URL parameter is required."}, status=status.HTTP_400_BAD_REQUEST)
            
        # 1. GATEKEEPER CHECK (Handles both connected and unconnected states cleanly)
        allowed, reason = validate_analysis_access(request.user, url)
        if not allowed:
            return Response({"error": reason}, status=status.HTTP_403_FORBIDDEN)
            
        # 2. PROCEED WITH ANALYSIS
        aggregator = DashboardAggregatorService(user=request.user)
        try:
            payload = aggregator.build_payload(url)
            
            # --- THE FIX: Inject GitHub AND GA4 connection status into the dashboard data ---
            has_integrations = hasattr(request.user, 'integrations')
            if has_integrations:
                integrations = request.user.integrations
                payload['is_github_connected'] = bool(integrations.github_repo_linked)
                # Add the missing GA4 boolean flag for the frontend UI:
                payload['is_ga_connected'] = bool(integrations.ga4_property_id or integrations.ga4_access_token)
            else:
                payload['is_github_connected'] = False
                payload['is_ga_connected'] = False
            # ------------------------------------------------------------------------

            critical_fixes = [item.get('title') for item in payload.get('critical_action_items', [])]
            suggestions = []
            if payload.get('enriched_statistics'):
                stats = payload['enriched_statistics']
                if stats.get('traffic_decay'):
                    suggestions.append(f"Traffic decay detected on {len(stats['traffic_decay'])} URLs.")
                if stats.get('mobile_penalty', {}).get('penalty_gap', 0) > 10:
                    suggestions.append("High mobile performance penalty detected.")

            AnalysisHistory.objects.create(
                user=request.user,
                url_analyzed=url,
                status=AnalysisHistory.StatusChoices.COMPLETED,
                seo_score=payload.get('overall_score'),
                recommendations_summary={
                    "critical_fixes": critical_fixes,
                    "suggestions": suggestions
                }
            )

            return Response(payload, status=status.HTTP_200_OK)
        except Exception as e:
            return Response({"error": str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

class AnalyzeURLView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        serializer = AnalysisHistorySerializer(data=request.data)
        if serializer.is_valid():
            analysis_record = serializer.save(user=request.user)
            # run_seo_analysis.delay(analysis_record.id)
            return Response(
                {"message": "Analysis started.", "data": serializer.data},
                status=status.HTTP_202_ACCEPTED
            )
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


class AnalysisHistoryListView(generics.ListAPIView):
    serializer_class = AnalysisHistorySerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        return AnalysisHistory.objects.filter(user=self.request.user)

class AnalysisHistoryDetailView(generics.RetrieveAPIView):
    serializer_class = AnalysisHistorySerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        return AnalysisHistory.objects.filter(user=self.request.user)

class IgnoreRecommendationView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        issue_type = request.data.get('issue_type')
        file_path = request.data.get('file_path')
        explanation = request.data.get('explanation', '')

        if not issue_type or not file_path:
            return Response({"error": "issue_type and file_path are required."}, status=status.HTTP_400_BAD_REQUEST)

        IgnoredRecommendation.objects.get_or_create(
            user=request.user,
            issue_type=issue_type,
            file_path=file_path,
            defaults={'explanation': explanation}
        )
        return Response({"message": "Recommendation ignored successfully."}, status=status.HTTP_200_OK)