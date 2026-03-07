# authentication/serializers.py
from rest_framework import serializers
from django.contrib.auth.models import User
#The serializer acts as a translator. It takes the JSON data sent from your Next.js form and securely saves it into Django's default database.
class RegisterSerializer(serializers.ModelSerializer):
    class Meta:
        model = User
        fields = ('id', 'username', 'email', 'password')
        extra_kwargs = {
            'password': {'write_only': True}, # Ensures the password is never sent back in a response
            'email': {'required': True}       # Makes the email field mandatory
        }

    def create(self, validated_data):
        # create_user automatically hashes and secures the password
        user = User.objects.create_user(
            username=validated_data['username'],
            email=validated_data['email'],
            password=validated_data['password']
        )
        return user