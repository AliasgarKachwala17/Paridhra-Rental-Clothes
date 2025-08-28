from django.contrib.auth import get_user_model
from django.core.mail import send_mail
from django.utils import timezone
from rest_framework import status, generics
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework_simplejwt.tokens import RefreshToken
from google.oauth2 import id_token
from google.auth.transport import requests

from .models import OTPRequest
from .serializers import SendOTPSerializer, VerifyOTPSerializer, GoogleLoginSerializer

User = get_user_model()

class SendOTPView(generics.GenericAPIView):
    serializer_class = SendOTPSerializer

    def post(self, request, *args, **kwargs):
        ser = self.get_serializer(data=request.data)
        ser.is_valid(raise_exception=True)
        email = ser.validated_data["email"]
        # create + email the OTP
        otp = OTPRequest.create_otp(email)
        send_mail(
            subject="Your login OTP",
            message=f"Your OTP code is {otp.code}. It expires in 10 minutes.",
            from_email=None,  # DEFAULT_FROM_EMAIL
            recipient_list=[email],
        )
        return Response({"detail": "OTP sent."}, status=status.HTTP_200_OK)


class VerifyOTPView(generics.GenericAPIView):
    serializer_class = VerifyOTPSerializer

    def post(self, request, *args, **kwargs):
        ser = self.get_serializer(data=request.data)
        ser.is_valid(raise_exception=True)
        email, code = ser.validated_data["email"], ser.validated_data["otp"]

        try:
            otp_obj = OTPRequest.objects.filter(email=email, code=code).latest("created_at")
        except OTPRequest.DoesNotExist:
            return Response({"detail": "Invalid OTP."}, status=status.HTTP_400_BAD_REQUEST)

        if otp_obj.is_expired():
            return Response({"detail": "OTP has expired."}, status=status.HTTP_400_BAD_REQUEST)

        # ✅ Always check if user exists by email
        user = User.objects.filter(email=email).first()
        if not user:
            user = User.objects.create(username=email, email=email, auth_provider="email")

        refresh = RefreshToken.for_user(user)
        return Response({
            "access": str(refresh.access_token),
            "refresh": str(refresh),
            "user": {
                "id": user.id,
                "email": user.email,
                "auth_provider": user.auth_provider,
            }
        }, status=status.HTTP_200_OK)



class GoogleLoginView(generics.GenericAPIView):
    serializer_class = GoogleLoginSerializer
    permission_classes = []  # allow anyone

    def post(self, request):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        token = serializer.validated_data["token"]

        try:
            # Verify token with Google
            idinfo = id_token.verify_oauth2_token(token, requests.Request())
            email = idinfo.get("email")
            name = idinfo.get("name")

            if not email:
                return Response({"error": "Google account has no email"}, status=status.HTTP_400_BAD_REQUEST)

            # ✅ Always check if user exists by email
            user = User.objects.filter(email=email).first()
            if user:
                # Update provider if necessary
                if user.auth_provider != "google":
                    user.auth_provider = "google"
                    user.save()
            else:
                # Create new user if not exist
                user = User.objects.create(
                    username=email,
                    email=email,
                    first_name=name,
                    auth_provider="google",
                )

            # ✅ Issue JWT
            refresh = RefreshToken.for_user(user)
            return Response({
                "access": str(refresh.access_token),
                "refresh": str(refresh),
                "user": {
                    "id": user.id,
                    "email": user.email,
                    "name": user.first_name,
                    "auth_provider": user.auth_provider,
                }
            })
        except Exception as e:
            return Response({"error": str(e)}, status=status.HTTP_400_BAD_REQUEST)
