# authentication/urls.py
from django.urls import path
from rest_framework_simplejwt.views import TokenObtainPairView, TokenRefreshView
from .views import RegisterView
from django.urls import include
urlpatterns = [
   
    # This built-in view handles checking the username & password and returning the login token
    path('login/', TokenObtainPairView.as_view(), name='token_obtain_pair'), 
    path('login/refresh/', TokenRefreshView.as_view(), name='token_refresh'),
    path('register/', RegisterView.as_view(), name='auth_register'),
]