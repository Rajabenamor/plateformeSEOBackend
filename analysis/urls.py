# analysis/urls.py
from django.urls import path
from .views import AnalyzeURLView , AnalysisHistoryListView , AnalysisHistoryDetailView

urlpatterns = [
    path('analyze/', AnalyzeURLView.as_view(), name='analyze-url'),
    path('history/', AnalysisHistoryListView.as_view(), name='analysis-history'),
    # Add the single detail route:
    path('history/<int:pk>/', AnalysisHistoryDetailView.as_view(), name='analysis-detail'),
]