from rest_framework import generics, status , serializers
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.decorators import api_view, permission_classes
from django.contrib.auth.models import User
from django.conf import settings
from django.core.signing import TimestampSigner, SignatureExpired, BadSignature
from rest_framework_simplejwt.tokens import RefreshToken
from rest_framework_simplejwt.views import TokenObtainPairView
from rest_framework_simplejwt.serializers import TokenObtainPairSerializer
from django.core.mail import send_mail
from django.core.cache import cache
import requests
import random
import logging
from django.core.mail import EmailMessage
from ..serializers import RegisterSerializer, UserSerializer, ChangePasswordSerializer
from ..services.google_service import GoogleService

signer = TimestampSigner()
logger = logging.getLogger(__name__)
class RegisterPendingView(APIView):
    """
    Alternative 1: Step 1 Registration
    Validates user credentials format and caches them without writing to DB.
    Sends out a 6-digit activation code.
    """
    permission_classes = [AllowAny]

    def post(self, request):
        serializer = RegisterSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
        
        validated_data = serializer.validated_data
        email = validated_data['email']
        username = validated_data['username']
        otp_code = f"{random.randint(100000, 999999)}"
        
        # Save temporary record to cache instead of database
        registration_data = {
            'username': username,
            'email': email,
            'password': validated_data['password'], 
            'otp': otp_code
        }
        
        cache_key = f"pending_user_{email}"
        cache.set(cache_key, registration_data, timeout=900)  # Valid for 15 minutes

        # Dispatch transactional email via Brevo Template
        try:
            message = EmailMessage(
                to=[email],
                # Brevo template handles the fallback body and subject natively
            )
            
            # Match this ID with the transactional template ID you create inside Brevo
            message.template_id = 5  
            
            # Map parameters for your custom HTML layout
            message.merge_global_data = {
                'username': username,
                'otp_code': otp_code
            }

            message.send(fail_silently=False)
            logger.info("Registration OTP verification email sent to %s via Brevo template 5.", email)

        except Exception as e:
            logger.error(
                "Failed to send registration OTP email to %s. Error: %s", 
                email, 
                str(e), 
                exc_info=True
            )
        return Response({"message": "OTP validation code sent to email successfully."}, status=status.HTTP_200_OK)


class VerifyOTPView(APIView):
    """
    Alternative 1: Step 2 Verification
    Validates the user code against the engine cache and creates the real user account.
    """
    permission_classes = [AllowAny]

    def post(self, request):
        email = request.data.get('email')
        otp_code = request.data.get('otp')

        if not email or not otp_code:
            return Response({"error": "Email and OTP code are required."}, status=status.HTTP_400_BAD_REQUEST)

        # Retrieve pending data from cache
        cache_key = f"pending_user_{email}"
        pending_user = cache.get(cache_key)

        if not pending_user:
            return Response({"error": "Verification session expired or user not found. Please register again."}, status=status.HTTP_400_BAD_REQUEST)

        # Check OTP match
        if pending_user['otp'] != otp_code:
            return Response({"error": "Invalid OTP verification code."}, status=status.HTTP_400_BAD_REQUEST)

        # Double check email hasn't been taken since cache storage started
        if User.objects.filter(email=email).exists():
            cache.delete(cache_key)
            return Response({"error": "A user with this email was registered while you were verifying."}, status=status.HTTP_400_BAD_REQUEST)

        # OTP is valid! Commit user to the Database atomically
        try:
            user = User.objects.create_user(
                username=pending_user['username'],
                email=pending_user['email'],
                password=pending_user['password'],
                is_active=True # Fully active immediately
            )
            
            # Clear cache memory data string
            cache.delete(cache_key)
            
            return Response({"message": "Account created and activated successfully!"}, status=status.HTTP_201_CREATED)
        except Exception as e:
            return Response({"error": f"Failed to finalize registration: {str(e)}"}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


class CustomTokenObtainPairSerializer(TokenObtainPairSerializer):
    @classmethod
    def get_token(cls, user):
        token = super().get_token(user)
        token['is_staff'] = user.is_staff
        token['is_superuser'] = user.is_superuser
        return token

    def validate(self, attrs):
        username = attrs.get(self.username_field)
        user = User.objects.filter(username=username).first()
        
        # If they are in the database but inactive, an admin blocked them.
        if user and not user.is_active:
            raise serializers.ValidationError(
                {'error': 'This account has been deactivated by an administrator. Please contact support.'}
            )
            
        data = super().validate(attrs)
        return data

class CustomTokenObtainPairView(TokenObtainPairView):
    serializer_class = CustomTokenObtainPairSerializer

class GoogleAuthView(APIView):
    permission_classes = [AllowAny]
    def post(self, request):
        credential = request.data.get('credential')
        if not credential:
            return Response({'error': 'Credential is required'}, status=status.HTTP_400_BAD_REQUEST)
        
        google_data = GoogleService.verify_token(credential)
        if not google_data:
            return Response({'error': 'Invalid Google token'}, status=status.HTTP_401_UNAUTHORIZED)

        email = google_data.get('email')
        if not email:
            return Response({'error': 'Email not provided by Google'}, status=status.HTTP_400_BAD_REQUEST)

        user, created = User.objects.get_or_create(
            email=email,
            defaults={
                'username': email.split('@')[0],
                'first_name': google_data.get('given_name', ''),
                'last_name': google_data.get('family_name', ''),
                'is_active': True,
            }
        )

        if not user.is_active:
            return Response({'error': 'Account is inactive.'}, status=status.HTTP_403_FORBIDDEN)

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
        })

class UserProfileView(generics.RetrieveAPIView):
    permission_classes = [IsAuthenticated]
    serializer_class = UserSerializer
    def get_object(self):
        return self.request.user

class ChangePasswordView(generics.UpdateAPIView):
    serializer_class = ChangePasswordSerializer
    permission_classes = [IsAuthenticated]
    def get_object(self, queryset=None):
        return self.request.user

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
        
        headers = {"api-key": settings.BREVO_API_KEY, "content-type": "application/json"}
        payload = {
            "to": [{"email": new_email}],
            "templateId": 1, 
            "params": {"link": verification_link, "firstname": user.username}
        }
        requests.post("https://api.brevo.com/v3/smtp/email", json=payload, headers=headers)
        response_data["message"] += "Verification link sent."
        response_data["email_pending"] = True
        
    return Response(response_data)

@api_view(['POST'])
@permission_classes([AllowAny])
def verify_email_change(request):
    token = request.data.get('token')
    try:
        data = signer.unsign_object(token, max_age=86400)
        user = User.objects.get(id=data['user_id'])
        user.email = data['new_email']
        user.save()
        return Response({"success": True, "message": "Email updated successfully.", "new_email": user.email})
    except (SignatureExpired, BadSignature):
        return Response({"success": False, "error": "Invalid or expired token."}, status=400)
    except User.DoesNotExist:
        return Response({"success": False, "error": "User not found."}, status=404)