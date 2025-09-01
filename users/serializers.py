from rest_framework import serializers
from django.contrib.auth import get_user_model

class SendOTPSerializer(serializers.Serializer):
    email = serializers.EmailField()

class VerifyOTPSerializer(serializers.Serializer):
    email = serializers.EmailField()
    otp   = serializers.CharField(max_length=6)

class GoogleLoginSerializer(serializers.Serializer):
    token = serializers.CharField()

User = get_user_model()

class UserSerializer(serializers.ModelSerializer):
    class Meta:
        model = User
        fields = [
            "id", "username", "email", "first_name", "last_name",
            "auth_provider", "is_staff",  "is_active", "date_joined"
        ]
