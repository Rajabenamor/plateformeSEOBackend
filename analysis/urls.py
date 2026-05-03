from django.urls import path
from .views import AnalyzeURLView , AnalysisHistoryListView , AnalysisHistoryDetailView, DashboardDataView

urlpatterns = [
    path('analyze/', AnalyzeURLView.as_view(), name='analyze-url'),
    path('history/', AnalysisHistoryListView.as_view(), name='analysis-history'),
    path('history/<int:pk>/', AnalysisHistoryDetailView.as_view(), name='analysis-detail'),
    path('dashboard-data/', DashboardDataView.as_view(), name='dashboard-data'),
]