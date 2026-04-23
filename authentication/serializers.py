# authentication/serializers.py
from rest_framework import serializers
from django.contrib.auth.models import User
from django.core.mail import send_mail
from django.conf import settings
from django.contrib.auth.password_validation import validate_password
#The serializer acts as a translator. It takes the JSON data sent from your Next.js form and securely saves it into Django's default database.
class RegisterSerializer(serializers.ModelSerializer):
    class Meta:
        model = User
        fields = ('id', 'username', 'email', 'password')
        extra_kwargs = {
            'password': {'write_only': True}, # Ensures the password is never sent back in a response
            'email': {'required': True}       # Makes the email field mandatory
        }
        # validate if the email already exist
    def validate_email(self, value):
        if User.objects.filter(email=value).exists():
            raise serializers.ValidationError("A user with that email already exists.")
        return value

    def create(self, validated_data):
        # create_user automatically hashes and secures the password
        user = User.objects.create_user(
            username=validated_data['username'],
            email=validated_data['email'],
            password=validated_data['password'],
            is_active=False
        )
        try:
            send_mail(
                subject="Registration Received - Action Required",
                message=f"Hi {user.username},\n\nThank you for registering! Your account has been created successfully.\nFor security reasons, an administrator must verify and activate your account before you can log in.\n\nYou will receive another email as soon as your account is active.",               
                from_email=settings.DEFAULT_FROM_EMAIL,
                recipient_list=[user.email],
                fail_silently=False
            )
        except Exception as e :
            print(f"Error sending registration email:{e}")
        return user

class UserSerializer(serializers.ModelSerializer):
    class Meta:
        model= User
        fields =[
            'id',
            'username',
            'email',
            'is_active',
            'is_staff',
            'date_joined',
        ]
        read_only_fields=['id','date_joined']
class UserUpdateSerializer(serializers.ModelSerializer):
    class Meta :
        model= User
        #the fields that will be updated 
        fields = ['id','username','email']
        read_only_fields=['id']

#user logged in changes his password in settings
class ChangePasswordSerializer(serializers.Serializer):
    old_password = serializers.CharField(required=True, write_only=True)
    new_password = serializers.CharField(required=True, write_only=True, validators=[validate_password])

    def validate_old_password(self, value):
        user = self.context['request'].user
        if not user.check_password(value):
            raise serializers.ValidationError("Your old password was entered incorrectly.")
        return value

    def save(self, **kwargs):
        user = self.context['request'].user
        user.set_password(self.validated_data['new_password'])
        user.save()
        return user