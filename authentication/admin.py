from django.contrib import admin
from django.contrib.auth.admin import UserAdmin
from .models import User,  UserIntegration

# Register your models here.


# Register the new Integrations model
@admin.register(UserIntegration)
class UserIntegrationAdmin(admin.ModelAdmin):
    list_display = ('user', 'has_github', 'has_ga4', 'created_at')
    search_fields = ('user__username', 'user__email')
    
    # Custom columns to easily see if tokens exist without exposing the raw token string
    def has_github(self, obj):
        return bool(obj.github_access_token)
    has_github.boolean = True
    has_github.short_description = 'GitHub Connected'

    def has_ga4(self, obj):
        return bool(obj.ga4_access_token)
    has_ga4.boolean = True
    has_ga4.short_description = 'GA4 Connected'
