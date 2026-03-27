import logging
from django.contrib.auth.models import User
from rest_framework import generics, status
from rest_framework.permissions import IsAdminUser
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework.pagination import PageNumberPagination
from .serializers import UserSerializer
from django.core.mail import send_mail
from django.conf import settings

logger = logging.getLogger(__name__)


#built-in generics handles everything
class UserListView(generics.ListAPIView):
    permission_classes= [IsAdminUser]
    serializer_class= UserSerializer
    queryset= User.objects.all().order_by('-date_joined')
    pagination_class= PageNumberPagination

#built-in destroy generics handles everything + custom safety checks
class UserDeleteView(generics.DestroyAPIView):
    permission_classes= [IsAdminUser]
    serializer_class= UserSerializer
    queryset= User.objects.all()
    lookup_field = 'id'
    lookup_url_kwarg='user_id'

    def perform_destroy(self, instance):
        #safety checks
        #prevents self deletion
        if instance == self.request.user:
            raise ValidationError('You cannot delete your own account')
        #only super admin can delete staff memebrs (sub admins)
        if instance.is_staff and not self.request.user.is_staff:
              raise PermissionDenied('Only the super admin can delete other admins.')
        
        logger.info(f"Admin '{self.request.user.username}' deleted '{instance.username}'")
        instance.delete()


#custom toggle 
class UsetToggleActiveView(APIView):
    permission_classes = [IsAdminUser]

    def patch(self,request,user_id):
        try:
            user= User.objects.get(id=user_id)
        except User.doesNotExist:
            return Response({'error': 'User not found'}, status=status.HTTP_404_NOT_FOUND)
        
        if user == request.user:
             return Response({'error': 'You cannot deactivate your own account'}, status=status.HTTP_400_BAD_REQUEST)
        #get the new status sent from the React frontend
        new_status = request.data.get('is_active')

        if new_status is None:
            return Response({'error': "'is_active' field is required"}, status=status.HTTP_400_BAD_REQUEST)
        #update and save the user
        user.is_active=new_status
        user.save()
        try :
            if user.is_active:
                #send the activated email
                 send_mail(
                    subject='Your Account has been Activated!',
                    message=f"Hi {user.username},\n\nYour account is now active. You can log in and start using the platform.\n\nBest regards,\nThe Admin Team",
                    from_email=settings.DEFAULT_FROM_EMAIL,
                    recipient_list=[user.email],
                    fail_silently=False # false to see brevo errors in the console
                )
            else :
                #send the deactivated email
                 send_mail(
                    subject='Your Account has been Deactivated!',
                    message=f"Hi {user.username},\n\nYour account has been  deacactivated by an administartor. If you believe this is a mistake, please contact support.",
                    from_email=settings.DEFAULT_FROM_EMAIL,
                    recipient_list=[user.email],
                    fail_silently=False # false to see brevo errors in the console
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

#create another admin
class CreateAdminView(APIView):
    permission_classes = [IsAdminUser]

    def post(self,request):
        username = request.data.get('username')
        password = request.data.get('password')

        #validate required fields
        if not username or not password:
            return Response(
                {'error': 'Username and password are required'},
                status= status.HTTP_400_BAD_REQUEST
            )
        #check if username already exists 
        if User.objects.filter(username=username).exists():
            return Response(
                {'error': 'Username already exists'},
                status= status.HTTP_400_BAD_REQUEST

        )
        #create admin user
        user = User.objects.create_user(
            username=username,
            password=password,
            is_staff=True, #makes them admin
            is_active=True,
        )

        logger.info(f"Admin '{request.user.username}' created new admin '{username}'")

        return Response(
            UserSerializer(user).data,
            status=status.HTTP_201_CREATED
        )
