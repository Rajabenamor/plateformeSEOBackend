import logging
from django.contrib.auth.models import User
from rest_framework import generics, status
from rest_framework.permissions import IsAdminUser
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework.pagination import PageNumberPagination
from .serializers import UserSerializer , UserUpdateSerializer
from django.core.mail import send_mail
from django.conf import settings

logger = logging.getLogger(__name__)


class UserListView(generics.ListAPIView):
    permission_classes= [IsAdminUser]
    serializer_class= UserSerializer
    queryset= User.objects.all().order_by('-date_joined')
    pagination_class= PageNumberPagination

class UserDeleteView(generics.DestroyAPIView):
    permission_classes= [IsAdminUser]
    serializer_class= UserSerializer
    queryset= User.objects.all()
    lookup_field = 'id'
    lookup_url_kwarg='user_id'

    def perform_destroy(self, instance):
        if instance == self.request.user:
            raise ValidationError('You cannot delete your own account')
        if instance.is_staff and not self.request.user.is_staff:
              raise PermissionDenied('Only the super admin can delete other admins.')
        
        logger.info(f"Admin '{self.request.user.username}' deleted '{instance.username}'")
        instance.delete()


class UsetToggleActiveView(APIView):
    permission_classes = [IsAdminUser]

    def patch(self,request,user_id):
        try:
            user= User.objects.get(id=user_id)
        except User.doesNotExist:
            return Response({'error': 'User not found'}, status=status.HTTP_404_NOT_FOUND)
        
        if user == request.user:
             return Response({'error': 'You cannot deactivate your own account'}, status=status.HTTP_400_BAD_REQUEST)
        new_status = request.data.get('is_active')

        if new_status is None:
            return Response({'error': "'is_active' field is required"}, status=status.HTTP_400_BAD_REQUEST)
        user.is_active=new_status
        user.save()
        try :
            if user.is_active:
                 send_mail(
                    subject='Your Account has been Activated!',
                    message=f"Hi {user.username},\n\nYour account is now active. You can log in and start using the platform.\n\nBest regards,\nThe Admin Team",
                    from_email=settings.DEFAULT_FROM_EMAIL,
                    recipient_list=[user.email],
                    fail_silently=False
                )
            else :
                 send_mail(
                    subject='Your Account has been Deactivated!',
                    message=f"Hi {user.username},\n\nYour account has been  deacactivated by an administartor. If you believe this is a mistake, please contact support.",
                    from_email=settings.DEFAULT_FROM_EMAIL,
                    recipient_list=[user.email],
                    fail_silently=False
                )

        except Exception as e:
            print(f"Error sending status update email: {e}")

        return Response({'message': f"User {user.username} status updated to {user.is_active}.",
        "is_active": user.is_active},
         status=status.HTTP_200_OK)

        action= 'activated ' if user.is_active else 'deactivated'
        user.is_active = not user.is_active
        user.save()

        logger.info(f"Admin '{self.request.user.username}' {action } '{user.username}'")

        return Response(UserSerializer(user).data, status=status.HTTP_200_OK)

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