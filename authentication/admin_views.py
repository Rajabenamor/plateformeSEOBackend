import logging
from django.contrib.auth.models import User
from rest_framework import generics, status
from rest_framework.permissions import IsAdminUser
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework.pagination import PageNumberPagination
from rest_framework.exceptions import ValidationError, PermissionDenied # FIXED: Added missing imports
from .serializers import UserSerializer , UserUpdateSerializer
from django.core.mail import EmailMessage
from django.conf import settings

logger = logging.getLogger(__name__)

class UserListView(generics.ListAPIView):
    permission_classes = [IsAdminUser]
    serializer_class = UserSerializer
    queryset = User.objects.all().order_by('-date_joined')
    pagination_class = PageNumberPagination

class UserDeleteView(generics.DestroyAPIView):
    permission_classes = [IsAdminUser]
    serializer_class = UserSerializer
    queryset = User.objects.all()
    lookup_field = 'id'
    lookup_url_kwarg = 'user_id'

    def perform_destroy(self, instance):
        if instance == self.request.user:
            raise ValidationError('You cannot delete your own account')
        if instance.is_staff and not self.request.user.is_staff:
              raise PermissionDenied('Only the super admin can delete other admins.')
        
        logger.info(f"Admin '{self.request.user.username}' deleted '{instance.username}'")
        instance.delete()


class UserToggleActiveView(APIView):
    permission_classes = [IsAdminUser]

    def patch(self, request, user_id):
        try:
            user = User.objects.get(id=user_id)
        except User.DoesNotExist: # FIXED: Correct capitalization
            return Response({'error': 'User not found'}, status=status.HTTP_404_NOT_FOUND)
        
        if user == request.user:
             return Response({'error': 'You cannot deactivate your own account'}, status=status.HTTP_400_BAD_REQUEST)
        
        new_status = request.data.get('is_active')

        if new_status is None:
            return Response({'error': "'is_active' field is required"}, status=status.HTTP_400_BAD_REQUEST)
        
        user.is_active = new_status
        user.save()
        # --- BREVO TEMPLATE EMAIL HANDLING ---
        if user.email:
            try:
                login_url = getattr(settings, 'FRONTEND_LOGIN_URL', 'http://localhost:3000/login')
                
                # Initialize the email message (Brevo template handles the subject and body)
                message = EmailMessage(
                    to=[user.email],
                    from_email=getattr(settings, 'DEFAULT_FROM_EMAIL', 'noreply@yourdomain.com')
                )
                
                # Pass dynamic variables to your Brevo template using {{ params.variable_name }}
                message.merge_global_data = {
                    'first_name': user.first_name or user.username,
                    'username': user.username,
                    'login_url': login_url
                }

                if user.is_active:
                    #Activation Template ID from Brevo
                    message.template_id = 3 
                else:
                    # Deactivation Template ID from Brevo
                    message.template_id = 4 

                message.send(fail_silently=False)
                logger.info(f"Status update email (Template {message.template_id}) sent to {user.email}")
                
            except Exception as e:
                logger.error(
                    "Failed to send status update email to %s. Error: %s", 
                    user.email, 
                    str(e), 
                    exc_info=True
                )
        else:
            logger.warning("No email address found for user '%s'. Skipping email notification.", user.username)

        action = 'activated' if user.is_active else 'deactivated'
        logger.info(f"Admin '{request.user.username}' {action} '{user.username}'")

        return Response({
            'message': f"User {user.username} status updated to {user.is_active}.",
            "is_active": user.is_active
        }, status=status.HTTP_200_OK)


class CreateUserView(APIView):
    permission_classes = [IsAdminUser]

    def post(self, request):
        username = request.data.get('username')
        password = request.data.get('password')
        email = request.data.get('email', '')
        
        is_staff = request.data.get('is_staff', False)
        is_superuser = request.data.get('is_superuser', False)
        is_active = request.data.get('is_active', False)

        if not username or not password:
            return Response(
                {'error': 'Username and password are required'},
                status=status.HTTP_400_BAD_REQUEST
            )
            
        if User.objects.filter(username=username).exists():
            return Response(
                {'error': 'Username already exists'},
                status=status.HTTP_400_BAD_REQUEST
            )
            
        if (is_staff or is_superuser) and not request.user.is_superuser:
            return Response(
                {'error': 'Only Super Admins can create other administrators.'},
                status=status.HTTP_403_FORBIDDEN
            )

        user = User.objects.create_user(
            username=username,
            email=email,
            password=password
        )
        
        user.is_staff = is_staff
        user.is_superuser = is_superuser
        user.is_active = is_active
        user.save()

        role_created = "super admin" if is_superuser else ("admin" if is_staff else "user")
        logger.info(f"Admin '{request.user.username}' created new {role_created} '{username}'")

        return Response(
            UserSerializer(user).data,
            status=status.HTTP_201_CREATED
        )

class UserUpdateView(generics.UpdateAPIView):
    """
    Dedicated view for updating a user.
    """
    permission_classes = [IsAdminUser]
    queryset = User.objects.all()
    serializer_class = UserUpdateSerializer
    lookup_field = 'id'
    lookup_url_kwarg = 'user_id'

    def perform_update(self, serializer):
        instance = self.get_object()
        if instance.is_superuser and not self.request.user.is_superuser:
            raise PermissionDenied("You cannot modify a super user.")
        
        serializer.save()
        logger.info(f"Admin '{self.request.user.username}' updated '{instance.username}'")