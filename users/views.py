from django.contrib.auth import get_user_model
from django.core.mail import send_mail
from django.utils import timezone
from rest_framework import status, generics
from rest_framework.response import Response
from rest_framework_simplejwt.tokens import RefreshToken

from .models import OTPRequest
from .serializers import SendOTPSerializer, VerifyOTPSerializer

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

        # fetch the latest matching OTP
        try:
            otp_obj = OTPRequest.objects.filter(email=email, code=code) \
                                        .latest("created_at")
        except OTPRequest.DoesNotExist:
            return Response({"detail": "Invalid OTP."},
                            status=status.HTTP_400_BAD_REQUEST)

        if otp_obj.is_expired():
            return Response({"detail": "OTP has expired."},
                            status=status.HTTP_400_BAD_REQUEST)

        # get or create user
        user, _ = User.objects.get_or_create(username=email, defaults={"email": email})
        # issue JWT
        refresh = RefreshToken.for_user(user)
        return Response({
            "access": str(refresh.access_token),
            "refresh": str(refresh),
        }, status=status.HTTP_200_OK)