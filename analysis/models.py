from django.db import models

from django.contrib.auth import get_user_model

User = get_user_model() 

class AnalysisHistory(models.Model):
    class StatusChoices(models.TextChoices):
        PENDING = 'PENDING', 'Pending'
        PROCESSING = 'PROCESSING', 'Processing'
        COMPLETED = 'COMPLETED', 'Completed'
        FAILED = 'FAILED', 'Failed'

    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='seo_history')
    url_analyzed = models.URLField()
    
    task_id = models.CharField(max_length=255, null=True, blank=True, help_text="Celery Task ID")
    status = models.CharField(
        max_length=20, 
        choices=StatusChoices.choices, 
        default=StatusChoices.PENDING
    )

    seo_score = models.IntegerField(null=True, blank=True)
    recommendations_summary = models.JSONField(default=dict, blank=True) 
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-created_at']
        verbose_name_plural = "Analysis Histories"

    def __str__(self):
        return f"{self.user.username} - {self.url_analyzed} [{self.status}]"

class IgnoredRecommendation(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='ignored_recommendations')
    issue_type = models.CharField(max_length=100)
    file_path = models.CharField(max_length=255)
    explanation = models.TextField(blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']
        unique_together = ('user', 'issue_type', 'file_path')

    def __str__(self):
        return f"{self.user.username} ignored {self.issue_type} on {self.file_path}"