from rest_framework import serializers

class SendOTPSerializer(serializers.Serializer):
    email = serializers.EmailField()

class VerifyOTPSerializer(serializers.Serializer):
    email = serializers.EmailField()
    otp   = serializers.CharField(max_length=6)

class GoogleLoginSerializer(serializers.Serializer):
    token = serializers.CharField()