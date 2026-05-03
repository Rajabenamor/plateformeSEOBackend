from rest_framework import generics
import requests
import uuid
import base64
import os
import google.generativeai as genai
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
from django.core.mail import send_mail
from rest_framework.permissions import AllowAny
from rest_framework.decorators import api_view, permission_classes
from django.core.signing import TimestampSigner, SignatureExpired, BadSignature
class RegisterView(generics.CreateAPIView):
    queryset = User.objects.all()
    permission_classes = (AllowAny,)
    serializer_class = RegisterSerializer

class CustomTokenObtainPairSerializer(TokenObtainPairSerializer):
    @classmethod
    def get_token(cls, user):
        token = super().get_token(user)
        token['is_staff'] = user.is_staff
        token['is_superuser'] = user.is_superuser
        return token
    def validate(self, attrs):
        username= attrs.get(self.username_field)
        user = User.objects.filter(username=username).first()
        if user and not user.is_active:
            raise serializers.ValidationError(
                {'error':'Your account is pending admin approval.Please check your email.'}
            )
        data = super().validate(attrs)
        data['is_staff'] = self.user.is_staff
        data['user'] = {
            'email': self.user.email,
            'username': f"{self.user.first_name} {self.user.last_name}".strip() or self.user.username,
            'plan': 'Free Plan'
        }
        
        return data
class CustomTokenObtainPairView(TokenObtainPairView):
    serializer_class = CustomTokenObtainPairSerializer

class GoogleAuthView(APIView):
    permission_classes = [AllowAny]
    def post(self,request):
        credential = request.data.get('credential')

        if not credential:
            return Response(
                {'error': 'Credential is required'},
                status=status.HTTP_400_BAD_REQUEST
            )
        try:
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
        try:
            user = User.objects.get(email=email)
        except User.DoesNotExist:
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
        return Response({
            'access': str(refresh.access_token),
            'refresh': str(refresh),
            'user': {
                'email': user.email,
                'username': f"{user.first_name} {user.last_name}".strip() or user.username,
                'plan': 'Free Plan'
            }
        }, status=status.HTTP_200_OK)


# for dashboard view
# views.py
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
    
    dashboard_data = calculate_seo_metrics(target_url)
    dashboard_payload = {"status": "success", "data": dashboard_data}
    
    if dashboard_data.get('overall_score', 0) > 0:
        cache.set(cache_key, dashboard_payload, 86400)

    return JsonResponse(dashboard_payload)

class UserProfileView(generics.RetrieveAPIView):
    """
    Handles GET and PATCH for the currently logged-in user.
    No ID is needed in the URL.
    """
    permission_classes = [IsAuthenticated]
    serializer_class = UserSerializer

    def get_object(self):
        return self.request.user

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

class IntegrationStatusView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        try:
            integrations = request.user.integrations
            
            return Response({
                "github_connected": bool(integrations.github_access_token),
                "github_repo": integrations.github_repo_linked, 
                "ga4_connected": bool(integrations.ga4_access_token),
                "ga4_property": integrations.ga4_property_id
            })
        except UserIntegration.DoesNotExist:
            return Response({
                "github_connected": False,
                "github_repo": None,
                "ga4_connected": False,
                "ga4_property": None
            })
class GithubExchangeView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        code = request.data.get('code')
        installation_id = request.data.get('installation_id')

        if not code:
            return Response({"error": "No authorization code provided."}, status=status.HTTP_400_BAD_REQUEST)

        try:
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

            integration, created = UserIntegration.objects.get_or_create(user=request.user)
            integration.github_access_token = access_token
            
            if installation_id:
                integration.github_repo_linked = installation_id 
                
            integration.save()


            return Response({"message": "GitHub connected successfully!"}, status=status.HTTP_200_OK)
        except Exception as e:
                print(f"CRITICAL GITHUB ERROR: {str(e)}") 
                return Response({"error": f"An internal server error occurred: {str(e)}"}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
        


class CreateGithubPRView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        fix_title = request.data.get('title', 'SEO Fix')
        fix_explanation = request.data.get('explanation', '')
        target_file_path = request.data.get('target_file', 'src/app/page.tsx')
        current_code = request.data.get('current_code')
        suggested_code = request.data.get('suggested_code')

        try:
            integration = request.user.integrations
            github_token = integration.github_access_token
            target_repo = integration.github_repo_linked 

            if not github_token or not target_repo:
                return Response({"error": "GitHub not connected or repo not selected."}, status=status.HTTP_403_FORBIDDEN)

            from .services.github_service import GitHubService
            result = GitHubService.create_pull_request(
                github_token=github_token,
                target_repo=target_repo,
                fix_title=fix_title,
                fix_explanation=fix_explanation,
                target_file_path=target_file_path,
                current_code=current_code,
                suggested_code=suggested_code
            )

            if result.get("success"):
                return Response({"message": "Success!", "pr_url": result.get("pr_url")}, status=status.HTTP_201_CREATED)
            else:
                return Response({"error": result.get("error")}, status=status.HTTP_400_BAD_REQUEST)

        except Exception as e:
            print(f"CRITICAL SERVER ERROR: {str(e)}")
            return Response({"error": f"Server error: {str(e)}"}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

class SaveGithubRepoView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        repo_name = request.data.get('repo_name')
        
        if not repo_name:
            return Response({"error": "Repository name is required."}, status=status.HTTP_400_BAD_REQUEST)

        try:
            integration = request.user.integrations
            
            integration.github_repo_linked = repo_name.strip()
            integration.save()
            
            return Response({"message": "Repository saved successfully!"}, status=status.HTTP_200_OK)
            
        except UserIntegration.DoesNotExist:
            return Response({"error": "GitHub is not connected yet."}, status=status.HTTP_400_BAD_REQUEST)


signer = TimestampSigner()

@api_view(['POST'])
@permission_classes([IsAuthenticated])
def update_profile(request):
    user = request.user
    new_username = request.data.get('username')
    new_email = request.data.get('email')

    response_data = {"success": True, "message": "", "email_pending": False}

    if new_username and new_username != user.username:
        user.username = new_username
        user.save()
        response_data["message"] += "Username updated successfully. "

    if new_email and new_email != user.email:
        if User.objects.filter(email=new_email).exists():
            return Response({"success": False, "error": "Email already in use"}, status=400)

        token = signer.sign_object({'user_id': user.id, 'new_email': new_email})

        verification_link = f"{settings.FRONTEND_URL}/verify-email?token={token}"

        brevo_url="https://api.brevo.com/v3/smtp/email"
        headers ={
            "accept": "application/json",
            "api-key": settings.BREVO_API_KEY,
            "content-type":"application/json"
        }
        payload = {
            "to": [{"email": new_email}],
            "templateId": 1, 
            "params": {
                "link": verification_link,
                "firstname": user.username
            }
        }
        response = requests.post(brevo_url, json=payload, headers=headers)
        print(response.json())
        response_data["message"] += "A verification link was sent to your new email."
        response_data["email_pending"] = True
        
    return Response(response_data)


@api_view(['POST'])
@permission_classes([AllowAny])
def verify_email_change(request):
    token = request.data.get('token')
    
    try:
        data = signer.unsign_object(token, max_age=86400)
        
        user = User.objects.get(id=data['user_id'])

        verified_new_email = data['new_email']

        user.email = verified_new_email
        user.save()
        
        return Response({"success": True, "message": "Email updated successfully.","new_email": verified_new_email})
        
    except (SignatureExpired, BadSignature):
        return Response({"success": False, "error": "Invalid or expired token."}, status=400)
    except User.DoesNotExist:
        return Response({"success": False, "error": "User no longer exists."}, status=404)