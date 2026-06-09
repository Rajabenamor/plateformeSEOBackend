import logging
from django.utils import timezone
from datetime import timedelta
from django.db.models import Avg , Count
from django.db.models.functions import TruncDate
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
from authentication.models import UserIntegration
from analysis.models import AnalysisHistory, IgnoredRecommendation
from django.contrib.auth import get_user_model
logger = logging.getLogger(__name__)
User = get_user_model()

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

class SuperAdminKPIView(APIView):
    permission_classes = [IsAdminUser]

    def get(self, request):
        now = timezone.now()
        seven_days_ago = now - timedelta(days=7)

        # --- 1. EXISTING KPI LOGIC ---
        total_users = User.objects.count()
        new_users_week = User.objects.filter(date_joined__gte=seven_days_ago).count()
        
        total_audits = AnalysisHistory.objects.count()
        avg_seo_score_raw = AnalysisHistory.objects.aggregate(Avg('seo_score'))['seo_score__avg']
        avg_seo_score = round(avg_seo_score_raw, 1) if avg_seo_score_raw else 0

        ga4_count = UserIntegration.objects.exclude(ga4_access_token__isnull=True).exclude(ga4_access_token__exact='').count()
        github_count = UserIntegration.objects.exclude(github_repo_linked__isnull=True).exclude(github_repo_linked__exact='').count()
        ignored_fixes = IgnoredRecommendation.objects.count()

        # --- 2. NEW LINE CHART DATA LOGIC ---
        # Generate the last 7 dates
        dates = [(now - timedelta(days=i)).date() for i in range(6, -1, -1)]

        # Get daily counts using TruncDate
        users_by_date = User.objects.filter(date_joined__gte=seven_days_ago) \
            .annotate(date=TruncDate('date_joined')) \
            .values('date') \
            .annotate(count=Count('id'))

        audits_by_date = AnalysisHistory.objects.filter(created_at__gte=seven_days_ago) \
            .annotate(date=TruncDate('created_at')) \
            .values('date') \
            .annotate(count=Count('id'))

        # Format into a clean array for the frontend chart
        chart_data = []
        for d in dates:
            u_count = next((item['count'] for item in users_by_date if item['date'] == d), 0)
            a_count = next((item['count'] for item in audits_by_date if item['date'] == d), 0)
            chart_data.append({
                "name": d.strftime("%b %d"), # e.g., "Jun 09"
                "New Users": u_count,
                "Audits Run": a_count
            })

        return Response({
            "users": {"total": total_users, "new_this_week": new_users_week},
            "audits": {"total": total_audits, "avg_score": avg_seo_score},
            "integrations": {"ga4": ga4_count, "github": github_count},
            "feedback": {"ignored_fixes": ignored_fixes},
            "chart_data": chart_data # <-- Sending the chart data
        })