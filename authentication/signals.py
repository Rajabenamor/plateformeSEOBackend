from django.dispatch import receiver
from django_rest_passwordreset.signals import reset_password_token_created
from django.core.mail import send_mail
from django.conf import settings
from django.template.loader import render_to_string



@receiver(reset_password_token_created)
def handle_password_token_created(sender,instance,reset_password_token , *args , **kwargs):
    """
    Listens for a password reset token to be created and sends an email to the user.
    Uses dynamic settings for production-ready decoupled architecture.
    """
    #this is the link to Next.js 
    #Pull the base URL dynamically from settings.py
    #if frontend_url isn't set , use localhost
    base_url =getattr(settings, 'FRONTEND_URL' , 'http://localhost:3000')
    reset_url=f"{base_url}/auth/reset-password?token={reset_password_token.key}"
    
    #put the data of html file in a dictionary
    context = {
        'username' : reset_password_token.user.username,
        'reset_password_url' : reset_url
    }


    my_html_content=render_to_string('email/user_reset_password.html' , context)

    #send the email via brevo smtp
    send_mail(
        subject="Password Reset for {title}".format(title="Strive"),
        message=f"Use this link to reset your password: {reset_url}",
        html_message = my_html_content,
        from_email=settings.DEFAULT_FROM_EMAIL,
        recipient_list=[reset_password_token.user.email],
        fail_silently=False,
    )