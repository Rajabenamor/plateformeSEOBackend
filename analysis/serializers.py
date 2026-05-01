from rest_framework import serializers
from .models import AnalysisHistory

class AnalysisHistorySerializer(serializers.ModelSerializer):
    class Meta:
        model = AnalysisHistory
        fields = [
            'id', 
            'url_analyzed', 
            'status', 
            'task_id', 
            'seo_score', 
            'recommendations_summary', 
            'created_at', 
            'updated_at'
        ]
        read_only_fields = [
            'id', 
            'status', 
            'task_id', 
            'seo_score', 
            'recommendations_summary', 
            'created_at', 
            'updated_at'
        ]