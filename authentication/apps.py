from django.apps import AppConfig


class AuthenticationConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'authentication'

    def ready(self):
        #this imports the signals when the app starts so the brevo email can be sent to the user
        import authentication.signals
