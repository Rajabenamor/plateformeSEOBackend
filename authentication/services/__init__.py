from .seo_calculator import SEOCalculatorService

def calculate_seo_metrics(url, user_ga4_property_id=None, user_oauth_token=None):
    """
    Deprecated: Use SEOCalculatorService.calculate_metrics instead.
    Maintaining for backward compatibility during refactor.
    """
    return SEOCalculatorService.calculate_metrics(url, user_ga4_property_id, user_oauth_token)
