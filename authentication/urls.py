# authentication/urls.py
from django.urls import path
from rest_framework_simplejwt.views import TokenObtainPairView, TokenRefreshView , TokenVerifyView
from .views import RegisterView , GoogleAuthView , CustomTokenObtainPairView
from django.urls import include
urlpatterns = [
   
    # This built-in view handles checking the username & password and returning the login token
    path('login/', CustomTokenObtainPairView.as_view(), name='token_obtain_pair'), 
    path('login/refresh/', TokenRefreshView.as_view(), name='token_refresh'),
    path('verify/', TokenVerifyView.as_view(), name='token_verify'),
    path('register/', RegisterView.as_view(), name='auth_register'),
    path('google/', GoogleAuthView.as_view(), name='google_auth' )
]