from django.urls import path
from rest_framework_simplejwt.views import TokenRefreshView, TokenVerifyView
from .views import auth_views, integration_views, dashboard_views

urlpatterns = [
    # Auth
    path('login/', auth_views.CustomTokenObtainPairView.as_view(), name='token_obtain_pair'), 
    path('login/refresh/', TokenRefreshView.as_view(), name='token_refresh'),
    path('verify/', TokenVerifyView.as_view(), name='token_verify'),
    path('register/', auth_views.RegisterView.as_view(), name='auth_register'),
    path('google/', auth_views.GoogleAuthView.as_view(), name='google_auth' ),
    path('users/me/', auth_views.UserProfileView.as_view(), name='user-profile'),
    path('users/update-profile/', auth_views.update_profile, name='update_profile'),
    path('users/verify-email/', auth_views.verify_email_change, name='verify_email_change'),
    path('users/change-password/', auth_views.ChangePasswordView.as_view(), name='change_password'),

    # Integrations
    path('users/integrations/status/', integration_views.IntegrationStatusView.as_view(), name='integration-status'),
    path('integrations/github/exchange/', integration_views.GithubExchangeView.as_view(), name='github-exchange'),
    path('integrations/github/create-pr/', integration_views.CreateGithubPRView.as_view(), name='github-create-pr'),
    path('integrations/github/save-repo/', integration_views.SaveGithubRepoView.as_view(), name='save-github-repo'),

    # Dashboard
    path('api/dashboard/', dashboard_views.dashboard_api, name='dashboard_api'),
]
