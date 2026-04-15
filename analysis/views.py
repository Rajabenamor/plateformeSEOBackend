from django.shortcuts import render

# Create your views here.
# analysis/views.py
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from .serializers import AnalysisHistorySerializer
from .models import AnalysisHistory
from rest_framework import generics


class AnalyzeURLView(APIView):
    # This ensures only logged-in users (from Next.js) can use this endpoint
    permission_classes = [IsAuthenticated] 

    def post(self, request):
        serializer = AnalysisHistorySerializer(data=request.data)
        
        if serializer.is_valid():
            # Save the record, attaching it to the logged-in user
            analysis_record = serializer.save(user=request.user)
            
        
             # This sends the work to Upstash -> Celery
            run_seo_analysis.delay(analysis_record.id) 
    
            # Immediately return the ID and PENDING status to Next.js
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
        # SECURITY BEST PRACTICE: 
        # Override the queryset to ONLY return records belonging to the user making the request.
        return AnalysisHistory.objects.filter(user=self.request.user)

class AnalysisHistoryDetailView(generics.RetrieveAPIView):
    """
    Returns the full details of a single SEO analysis (including AI recommendations).
    """
    serializer_class = AnalysisHistorySerializer
    permission_classes = [IsAuthenticated]
    
    def get_queryset(self):
        # SECURITY: Only allow the user to retrieve their own reports!
        return AnalysisHistory.objects.filter(user=self.request.user)