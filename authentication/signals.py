import logging
from django.dispatch import receiver
from django.conf import settings
from django.core.mail import EmailMessage
from django_rest_passwordreset.signals import reset_password_token_created

logger = logging.getLogger(__name__)

@receiver(reset_password_token_created)
def handle_password_token_created(sender, instance, reset_password_token, *args, **kwargs):
    """
    this function represents the password reset flow + Password reset link dispatch via brevo 
    """
    user = reset_password_token.user
    
    if not user.email:
        logger.warning("Password reset failed: User %s has no email address.", user.username)
        return

    base_url = getattr(settings, 'FRONTEND_URL', 'http://localhost:3000')
    reset_url = f"{base_url}/auth/reset-password?token={reset_password_token.key}"

    try:
        message = EmailMessage(
            to=[user.email],
            # the Brevo template handles the fallback body and subject natively
        )
        
        # Anymail seamlessly maps these directly to Brevo's API parameters
        message.template_id = 2 
        message.merge_global_data = {
            'username': user.username,
            'reset_password_url': reset_url
        }

        message.send(fail_silently=False)
        logger.info("Password reset email sent to %s via Brevo template 2.", user.email)

    except Exception as e:
        logger.error(
            "Failed to send password reset email to %s. Error: %s", 
            user.email, 
            str(e), 
            exc_info=True
        )










# import json
# import logging
# from django.dispatch import receiver
# from django.conf import settings
# from django.core.mail import EmailMessage
# from django_rest_passwordreset.signals import reset_password_token_created

# logger = logging.getLogger(__name__)

# @receiver(reset_password_token_created)
# def handle_password_token_created(sender, instance, reset_password_token, *args, **kwargs):
#     user = reset_password_token.user
#     user_email = user.email

#     if not user_email:
#         logger.warning("Password reset failed: User %s has no email address.", user.username)
#         return

#     try:
#         target_template_id = 2 
#         base_url = getattr(settings, 'FRONTEND_URL', 'http://localhost:3000')
#         reset_url = f"{base_url}/auth/reset-password?token={reset_password_token.key}"
        
#         # 1. Create the JSON payload that Brevo's SMTP server will intercept
#         brevo_api_payload = {
#             "templateId": target_template_id,
#             "params": {
#                 "username": user.username,
#                 "reset_password_url": reset_url
#             }
#         }

#         # 2. Initialize the standard Django EmailMessage
#         message = EmailMessage(
#             subject="Reset your Strive password", # Fallback subject
#             body="Please view this email in an HTML-compatible client.", # Fallback body
#             to=[user_email],
#             from_email=getattr(settings, 'DEFAULT_FROM_EMAIL', 'noreply@yourdomain.com'),
            
#             # 3. Inject the payload into the custom X-SIB-API header
#             headers={
#                 "X-SIB-API": json.dumps(brevo_api_payload)
#             }
#         )

#         message.send(fail_silently=False)
#         logger.info("Password reset email sent to %s via Brevo template %s.", user_email, target_template_id)

#     except Exception as e:
#         logger.error(
#             "Failed to send password reset email to %s. Error: %s", 
#             user_email, 
#             str(e), 
#             exc_info=True
#         )
