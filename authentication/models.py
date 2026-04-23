from django.db import models
from django.contrib.auth import get_user_model
from django.db.models.signals import post_save
from django.dispatch import receiver


# Create your models here.

User = get_user_model()

# ... Your existing User model or AnalysisHistory model ...

class UserIntegration(models.Model):
    # Links directly to your user. related_name='integrations' allows us to do `request.user.integrations`
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='integrations')
    
    # GitHub Integration Fields
    github_access_token = models.CharField(max_length=255, blank=True, null=True)
    github_repo_linked = models.CharField(max_length=255, blank=True, null=True) # Useful for later!
    
    # GA4 Integration Fields
    ga4_access_token = models.CharField(max_length=255, blank=True, null=True)
    ga4_refresh_token = models.CharField(max_length=255, blank=True, null=True) # Google tokens expire, so we need a refresh token
    ga4_property_id = models.CharField(max_length=255, blank=True, null=True)
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"{self.user.username}'s Integrations"
    #automatically create an empty UserIntegration row whenever a new user signs up.
    @receiver(post_save, sender=User)
    def create_user_integration(sender, instance, created, **kwargs):
        if created:
            UserIntegration.objects.create(user=instance)