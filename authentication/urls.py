# authentication/urls.py
from django.urls import path
from rest_framework_simplejwt.views import TokenObtainPairView, TokenRefreshView , TokenVerifyView
from .views import RegisterView , GoogleAuthView , CustomTokenObtainPairView , UserProfileView , IntegrationStatusView , GithubExchangeView
from django.urls import include
from . import views

urlpatterns = [
   
    # This built-in view handles checking the username & password and returning the login token
    path('login/', CustomTokenObtainPairView.as_view(), name='token_obtain_pair'), 
    path('login/refresh/', TokenRefreshView.as_view(), name='token_refresh'),
   
    path('verify/', TokenVerifyView.as_view(), name='token_verify'),
    path('register/', RegisterView.as_view(), name='auth_register'),
    path('google/', GoogleAuthView.as_view(), name='google_auth' ),
    path('api/dashboard/', views.dashboard_api, name='dashboard_api'),
    #user updates his own profile
    path('users/me/', UserProfileView.as_view(), name='user-profile'),
    #user intgration of ga4 and github 
    path('users/integrations/status/', IntegrationStatusView.as_view(), name='integration-status'),
    path('integrations/github/exchange/', GithubExchangeView.as_view(), name='github-exchange'),
]
