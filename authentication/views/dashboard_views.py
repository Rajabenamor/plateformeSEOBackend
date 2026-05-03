from django.http import JsonResponse
from django.core.cache import cache
from ..services.seo_calculator import SEOCalculatorService

def dashboard_api(request):
    target_url = request.GET.get('url')
    force_refresh = request.GET.get('refresh') == 'true'

    if not target_url:
        return JsonResponse({"status": "error", "message": "URL parameter is required"}, status=400)
    
    safe_url_key = target_url.replace("https://", "").replace("http://", "").replace("/", "_")
    cache_key = f'dashboard_data_{safe_url_key}'
    
    if not force_refresh:
        cached_data = cache.get(cache_key)
        if cached_data: 
            return JsonResponse(cached_data)
    
    dashboard_data = SEOCalculatorService.calculate_metrics(target_url)
    dashboard_payload = {"status": "success", "data": dashboard_data}
    
    if dashboard_data.get('overall_score', 0) > 0:
        cache.set(cache_key, dashboard_payload, 86400)

    return JsonResponse(dashboard_payload)
