from django.urls import path
from .views import SendOTPView, VerifyOTPView, GoogleLoginView

urlpatterns = [
    path("send-otp/", SendOTPView.as_view(), name="send-otp"),
    path("verify-otp/", VerifyOTPView.as_view(), name="verify-otp"),
    path("google-login/", GoogleLoginView.as_view(), name="google-login"),
]