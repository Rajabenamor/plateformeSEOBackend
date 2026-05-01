from rest_framework import generics
import requests
import uuid
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
            'username': f"{self.user.first_name} {self.user.last_name}".strip() or self.user.username,
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
                'username': f"{user.first_name} {user.last_name}".strip() or user.username,
                'plan': 'Free Plan' # Default plan for new Google sign-ups
            }
        }, status=status.HTTP_200_OK)


# for dashboard view
# views.py
def dashboard_api(request):
    target_url = request.GET.get('url')
    force_refresh = request.GET.get('refresh') == 'true' # <-- NEW: Check for refresh flag

    if not target_url:
        return JsonResponse({"status": "error", "message": "URL parameter is required"}, status=400)
    
    safe_url_key = target_url.replace("https://", "").replace("http://", "").replace("/", "_")
    cache_key = f'dashboard_data_{safe_url_key}'
    
    # <-- NEW: Only check cache if we aren't refreshing
    if not force_refresh:
        cached_data = cache.get(cache_key)
        if cached_data: 
            return JsonResponse(cached_data)
    
    dashboard_data = calculate_seo_metrics(target_url)
    dashboard_payload = {"status": "success", "data": dashboard_data}
    
    # <-- NEW: Only cache if the scan actually worked
    if dashboard_data.get('overall_score', 0) > 0:
        cache.set(cache_key, dashboard_payload, 86400)

    return JsonResponse(dashboard_payload)

#user updates his own profile
class UserProfileView(generics.RetrieveAPIView):
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
            integrations = request.user.integrations
            
            return Response({
                "github_connected": bool(integrations.github_access_token),
                # Add this line to send the linked repo to Next.js
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
                # THIS WILL PRINT THE REAL ERROR TO YOUR DJANGO TERMINAL
                print(f"CRITICAL GITHUB ERROR: {str(e)}") 
                return Response({"error": f"An internal server error occurred: {str(e)}"}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
        

class CreateGithubPRView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        fix_title = request.data.get('title', 'SEO Fix')
        code_fix = request.data.get('code_fix', '')
        
        # Grab the target file the AI suggested
        target_file_path = request.data.get('target_file', 'index.html')
        
        random_id = uuid.uuid4().hex[:6]

        try:
            integration = request.user.integrations
            github_token = integration.github_access_token
            target_repo = integration.github_repo_linked 

            if not github_token or not target_repo:
                return Response({"error": "GitHub not connected or repo not selected."}, status=status.HTTP_403_FORBIDDEN)

            headers = {
                "Authorization": f"token {github_token}",
                "Accept": "application/vnd.github.v3+json"
            }

            # 1. Get default branch
            repo_res = requests.get(f"https://api.github.com/repos/{target_repo}", headers=headers)
            default_branch = repo_res.json().get("default_branch", "main")

            # 2. Get the SHA of the latest commit
            ref_res = requests.get(f"https://api.github.com/repos/{target_repo}/git/refs/heads/{default_branch}", headers=headers)
            latest_sha = ref_res.json()['object']['sha']

            # 3. Create a new branch
            new_branch_name = f"strive-seo-fix-{random_id}"
            requests.post(
                f"https://api.github.com/repos/{target_repo}/git/refs",
                headers=headers,
                json={"ref": f"refs/heads/{new_branch_name}", "sha": latest_sha}
            )

            # 4. Check if the target file actually exists so we can overwrite it
            file_url = f"https://api.github.com/repos/{target_repo}/contents/{target_file_path}?ref={new_branch_name}"
            file_res = requests.get(file_url, headers=headers)
            
            import base64
            encoded_code = base64.b64encode(code_fix.encode('utf-8')).decode('utf-8')
            
            commit_data = {
                "message": f"Strive AI SEO Fix: {fix_title}",
                "content": encoded_code,
                "branch": new_branch_name
            }
            
            # If the file exists, GitHub REQUIRES its SHA to overwrite it
            if file_res.status_code == 200:
                commit_data["sha"] = file_res.json().get("sha")

            # 5. Commit the code to that specific file
            commit_res = requests.put(
                f"https://api.github.com/repos/{target_repo}/contents/{target_file_path}",
                headers=headers,
                json=commit_data
            )

            if commit_res.status_code not in [200, 201]:
                return Response({"error": f"Commit failed: {commit_res.json().get('message')}"}, status=status.HTTP_400_BAD_REQUEST)

            # 6. Open the Pull Request
            pr_data = {
                "title": f"🚀 Strive SEO Auto-Fix: {fix_title}",
                "body": f"This PR was generated automatically by Strive AI.\n\n**File modified:** `{target_file_path}`\n\nReview the code snippet before merging.",
                "head": new_branch_name,
                "base": default_branch
            }
            pr_response = requests.post(f"https://api.github.com/repos/{target_repo}/pulls", headers=headers, json=pr_data)
            
            if pr_response.status_code == 201:
                return Response({"message": "Success!", "pr_url": pr_response.json().get("html_url")}, status=status.HTTP_201_CREATED)
            else:
                return Response({"error": pr_response.json().get('message')}, status=status.HTTP_400_BAD_REQUEST)

        except Exception as e:
            return Response({"error": f"Server error: {str(e)}"}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

class SaveGithubRepoView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        repo_name = request.data.get('repo_name')
        
        if not repo_name:
            return Response({"error": "Repository name is required."}, status=status.HTTP_400_BAD_REQUEST)

        try:
            # Find the user's integration row
            integration = request.user.integrations
            
            # Save the typed repository name
            integration.github_repo_linked = repo_name.strip()
            integration.save()
            
            return Response({"message": "Repository saved successfully!"}, status=status.HTTP_200_OK)
            
        except UserIntegration.DoesNotExist:
            return Response({"error": "GitHub is not connected yet."}, status=status.HTTP_400_BAD_REQUEST)


#profile settings 
signer = TimestampSigner()

@api_view(['POST'])
@permission_classes([IsAuthenticated])
def update_profile(request):
    user = request.user
    new_username = request.data.get('username')
    new_email = request.data.get('email')

    response_data = {"success": True, "message": "", "email_pending": False}

    # 1. Update Username immediately 
    if new_username and new_username != user.username:
        user.username = new_username
        user.save()
        response_data["message"] += "Username updated successfully. "

    # 2. Handle Email Change securely (FIXED INDENTATION)
    if new_email and new_email != user.email:
        if User.objects.filter(email=new_email).exists():
            return Response({"success": False, "error": "Email already in use"}, status=400)

        # Generate a secure token containing user ID and the new Email
        token = signer.sign_object({'user_id': user.id, 'new_email': new_email})

        # Example: http://localhost:3000/verify-email?token=abc
        verification_link = f"{settings.FRONTEND_URL}/verify-email?token={token}"

        #set Up Brevo API 
        brevo_url="https://api.brevo.com/v3/smtp/email"
        headers ={
            "accept": "application/json",
            "api-key": settings.BREVO_API_KEY,
            "content-type":"application/json"
        }
        #tell brevo which template to use
        payload = {
            "to": [{"email": new_email}],
            "templateId": 1, 
            "params": {
                "link": verification_link, # This injects your URL into {{ params.link }}
                "firstname": user.username
            }
        }
        # 4. Fire the request!
        response = requests.post(brevo_url, json=payload, headers=headers)
        # (Optional) Print the response to your terminal so you can see if it worked
        print(response.json())
        response_data["message"] += "A verification link was sent to your new email."
        response_data["email_pending"] = True
        
    # FIXED INDENTATION: This must happen regardless of what was updated
    return Response(response_data)


@api_view(['POST'])
@permission_classes([AllowAny])
def verify_email_change(request):
    # FIXED TYPO
    token = request.data.get('token')
    
    try:
        # Token is valid for 24 hours (86400 seconds)
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