from celery import shared_task
from .models import AnalysisHistory

from authentication.services import calculate_seo_metrics

@shared_task
def run_seo_analysis(analysis_id):
    record = AnalysisHistory.objects.get(id=analysis_id)
    record.status = 'PROCESSING'
    record.save()

    results = calculate_seo_metrics(record.url_analyzed, user=record.user)

    record.seo_score = results['overall_score']
    record.recommendations_summary = {
        "fixes": results['seo_fixes'],
        "health": results['technical_health']
    }
    record.status = 'COMPLETED'
    record.save()