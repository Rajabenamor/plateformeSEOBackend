from rest_framework import generics, status
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
import requests

from ..serializers import RegisterSerializer, UserSerializer, ChangePasswordSerializer
from ..services.google_service import GoogleService

signer = TimestampSigner()

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
        data = super().validate(attrs)
        if not self.user.is_active:
             return Response({'error':'Your account is pending admin approval.'}, status=status.HTTP_403_FORBIDDEN)
        
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
