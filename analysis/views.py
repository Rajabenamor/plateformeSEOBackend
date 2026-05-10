from django.shortcuts import render

from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from .serializers import AnalysisHistorySerializer
from .models import AnalysisHistory, IgnoredRecommendation
from rest_framework import generics
from .services.dashboard_aggregator import DashboardAggregatorService


class AnalyzeURLView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        serializer = AnalysisHistorySerializer(data=request.data)

        if serializer.is_valid():
            analysis_record = serializer.save(user=request.user)

            # Assuming run_seo_analysis is imported elsewhere or handled by celery
            # run_seo_analysis.delay(analysis_record.id)

            return Response(
                {
                    "message": "Analysis started.",
                    "data": serializer.data
                },
                status=status.HTTP_202_ACCEPTED
            )

        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


class AnalysisHistoryListView(generics.ListAPIView):
    """
    Returns a list of all SEO analyses for the logged-in user.
    """
    serializer_class = AnalysisHistorySerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        return AnalysisHistory.objects.filter(user=self.request.user)

class AnalysisHistoryDetailView(generics.RetrieveAPIView):
    """
    Returns the full details of a single SEO analysis (including AI recommendations).
    """
    serializer_class = AnalysisHistorySerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        return AnalysisHistory.objects.filter(user=self.request.user)

class DashboardDataView(APIView):
    """
    Returns the aggregated intelligence payload for the dashboard.
    """
    permission_classes = [IsAuthenticated]

    def get(self, request):
        url = request.query_params.get('url')
        if not url:
            return Response({"error": "URL parameter is required."}, status=status.HTTP_400_BAD_REQUEST)
            
        aggregator = DashboardAggregatorService(user=request.user)
        try:
            payload = aggregator.build_payload(url)
            return Response(payload, status=status.HTTP_200_OK)
        except Exception as e:
            return Response({"error": str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

class IgnoreRecommendationView(APIView):
    """
    Saves an ignored recommendation so the AI doesn't suggest it again.
    """
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