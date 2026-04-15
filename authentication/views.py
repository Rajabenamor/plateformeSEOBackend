from rest_framework import generics
from rest_framework.permissions import AllowAny
from django.contrib.auth.models import User
from .serializers import RegisterSerializer , UserSerializer , ChangePasswordSerializer
from google.oauth2 import id_token
from django.conf import settings
from rest_framework import status 
from google.auth.transport import requests as google_requests
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework_simplejwt.tokens import RefreshToken
from rest_framework_simplejwt.serializers import TokenObtainPairSerializer
from rest_framework_simplejwt.views import TokenObtainPairView
from rest_framework import serializers
from django.core.cache import cache
from django.http import JsonResponse
from .services import calculate_seo_metrics
from rest_framework.permissions import IsAuthenticated
from .models import UserIntegration
class RegisterView(generics.CreateAPIView):
    queryset = User.objects.all()
    permission_classes = (AllowAny,) # Allows anyone (even guests) to access the registration page
    serializer_class = RegisterSerializer

#custom for logging to pass is_staff=true with the token 
class CustomTokenObtainPairSerializer(TokenObtainPairSerializer):
    @classmethod
    def get_token(cls, user):
        token = super().get_token(user)
        token['is_staff'] = user.is_staff  # ← inject is_staff into token
        token['is_superuser'] = user.is_superuser
        return token
    def validate(self, attrs):
        #find the user to check status before standard validation
        username= attrs.get(self.username_field)
        user = User.objects.filter(username=username).first()
        if user and not user.is_active:
            raise serializers.ValidationError(
                {'error':'Your account is pending admin approval.Please check your email.'}
            )
        data = super().validate(attrs)
        data['is_staff'] = self.user.is_staff  # ← add to response too
        # --- NEW: Send user data to Next.js ---
        # .strip() handles cases where a user might only have a first name
        # "or self.user.username" provides a fallback if they haven't set a name at all
        data['user'] = {
            'email': self.user.email,
            'full_name': f"{self.user.first_name} {self.user.last_name}".strip() or self.user.username,
            'plan': 'Free Plan' # You can tie this to a real Subscription model later
        }
        
        return data
class CustomTokenObtainPairView(TokenObtainPairView):
    serializer_class = CustomTokenObtainPairSerializer

#google auth for google sign in 
class GoogleAuthView(APIView):
    permission_classes = [AllowAny]
    def post(self,request):
        credential = request.data.get('credential') # ID token from google

        if not credential:
            return Response(
                {'error': 'Credential is required'},
                status=status.HTTP_400_BAD_REQUEST
            )
        try:
            #verify ID token locally - no extra network call to google
            google_data=id_token.verify_oauth2_token(
                credential,
                google_requests.Request(),
                settings.GOOGLE_CLIENT_ID
            )
        except ValueError:
            return Response(
                {'error':'Invalid Google token'},
                status=status.HTTP_401_UNAUTHORIZED
            )
        email=google_data.get('email')
        first_name=google_data.get('given_name','')
        last_name=google_data.get('family_name','')

        if not email:
            return Response(
                {'error':'Email not provided by Google'},
                status=status.HTTP_400_BAD_REQUEST
            )
        #looking for user by email first
        try:
            user = User.objects.get(email=email)
            #user exist - log them in , without creating a new account
        except User.DoesNotExist:
            #user doesnt exist , create account
            #remove it ? since google users are active by default
            user = User.objects.create_user(
                username=email.split('@')[0],
                email=email,
                first_name=first_name,
                last_name=last_name,
                is_active=True,
            )

        if not user.is_active:
            return Response(
                {'error':'Account is inactive. Contact admin'},
                status=status.HTTP_403_FORBIDDEN
            )
        refresh = RefreshToken.for_user(user)
        refresh['is_staff'] = user.is_staff
       # --- NEW: Send user data to Next.js ---
        return Response({
            'access': str(refresh.access_token),
            'refresh': str(refresh),
            'user': {
                'email': user.email,
                'full_name': f"{user.first_name} {user.last_name}".strip() or user.username,
                'plan': 'Free Plan' # Default plan for new Google sign-ups
            }
        }, status=status.HTTP_200_OK)


# for dashboard view
def dashboard_api(request):
    # Grab the URL from the frontend request 
    target_url = request.GET.get('url')
    if not target_url:
        return JsonResponse({"status": "error", "message": "URL parameter is required"}, status=400)
    
    # Create a unique cache key for this specific URL
    safe_url_key = target_url.replace("https://", "").replace("http://", "").replace("/", "_")
    cache_key = f'dashboard_data_{safe_url_key}'
    cached_data = cache.get(cache_key)
    
    if cached_data: 
        return JsonResponse(cached_data)
    
    """
    This view serves as the single endpoint for your frontend dashboard.
    """
    
    # 1. Call our new unified service function that handles Zyte, GA4, PageSpeed, OpenPageRank, and Gemini AI all at once!
    dashboard_data = calculate_seo_metrics(target_url)

    # 2. Package everything neatly into one Python dictionary. 
    # Because `calculate_seo_metrics` already formats the data perfectly, we just pass it straight in.
    dashboard_payload = {
        "status": "success",
        "data": dashboard_data
    }
    
    # 3. Save the result in the cache for 24 hours (86400 seconds)
    cache.set(cache_key, dashboard_payload, 86400)

    # 4. Return the data to the browser as a JSON response
    return JsonResponse(dashboard_payload)

#user updates his own profile
class UserProfileView(generics.RetrieveUpdateAPIView):
    """
    Handles GET and PATCH for the currently logged-in user.
    No ID is needed in the URL.
    """
    permission_classes = [IsAuthenticated]
    serializer_class = UserSerializer

    def get_object(self):
        # This is the ultimate security check. 
        # It ignores the URL completely and grabs the user from the JWT token.
        return self.request.user

#view for logged in user to change his password in settings
class ChangePasswordView(generics.UpdateAPIView):
    """
    An endpoint for changing password.
    """
    serializer_class = ChangePasswordSerializer
    permission_classes = [IsAuthenticated]

    def get_object(self, queryset=None):
        return self.request.user

    def update(self, request, *args, **kwargs):
        self.object = self.get_object()
        serializer = self.get_serializer(data=request.data)

        if serializer.is_valid():
            serializer.save()
            return Response({"message": "Password updated successfully."}, status=status.HTTP_200_OK)

        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

#the user integration og ga4 and github 
class IntegrationStatusView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        try:
            # Try to get the user's integrations
            integrations = request.user.integrations
            
            return Response({
                "github_connected": bool(integrations.github_access_token),
                "ga4_connected": bool(integrations.ga4_access_token)
            })
        except UserIntegration.DoesNotExist:
            # If the row doesn't exist yet, nothing is connected
            return Response({
                "github_connected": False,
                "ga4_connected": False
            })

class GithubExchangeView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        # 1. Grab the Ticket (code) and Installation ID from Next.js
        code = request.data.get('code')
        installation_id = request.data.get('installation_id')

        if not code:
            return Response({"error": "No authorization code provided."}, status=status.HTTP_400_BAD_REQUEST)

        try:
            # 2. Exchange the temporary code for a permanent Access Token
            # Note: You need to add GITHUB_CLIENT_ID and GITHUB_CLIENT_SECRET to your Django settings.py
            github_response = requests.post(
                'https://github.com/login/oauth/access_token',
                headers={'Accept': 'application/json'},
                data={
                    'client_id': settings.GITHUB_CLIENT_ID,
                    'client_secret': settings.GITHUB_CLIENT_SECRET,
                    'code': code,
                }
            )
            
            github_data = github_response.json()
            access_token = github_data.get('access_token')

            if not access_token:
                return Response({"error": "GitHub denied the token exchange."}, status=status.HTTP_400_BAD_REQUEST)

            # 3. Save the tokens to the database model we just built
            integration, created = UserIntegration.objects.get_or_create(user=request.user)
            integration.github_access_token = access_token
            
            # Save the installation_id. This is crucial for GitHub Apps so Strive 
            # knows exactly which repos it is allowed to edit.
            if installation_id:
                integration.github_repo_linked = installation_id 
                
            integration.save()

            return Response({"message": "GitHub connected successfully!"}, status=status.HTTP_200_OK)

        except Exception as e:
            return Response({"error": "An internal server error occurred."}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)