# authentication/serializers.py
from rest_framework import serializers
from django.contrib.auth.models import User
from django.core.mail import send_mail
from django.conf import settings
from django.contrib.auth.password_validation import validate_password
import random
from django.core.cache import cache

class RegisterSerializer(serializers.ModelSerializer):
    class Meta:
        model = User
        fields = ('id', 'username', 'email', 'password')
        extra_kwargs = {
            'password': {'write_only': True},
            'email': {'required': True}
        }

    def validate_email(self, value):
        if User.objects.filter(email=value).exists():
            raise serializers.ValidationError("A user with that email already exists.")
        return value

 

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
        fields = ['id','username','email']
        read_only_fields=['id']

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