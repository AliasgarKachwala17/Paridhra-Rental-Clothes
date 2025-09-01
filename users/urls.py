from django.urls import path, include
from rest_framework.routers import DefaultRouter

from .views import SendOTPView, VerifyOTPView, GoogleLoginView, UserViewSet


router = DefaultRouter()
router.register("list", UserViewSet, basename="user-list")


urlpatterns = [
    path("send-otp/", SendOTPView.as_view(), name="send-otp"),
    path("verify-otp/", VerifyOTPView.as_view(), name="verify-otp"),
    path("google-login/", GoogleLoginView.as_view(), name="google-login"),
    path("", include(router.urls)),
]