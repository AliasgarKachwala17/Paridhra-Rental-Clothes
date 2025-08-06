from django.urls import path
from rest_framework.routers import DefaultRouter
from .views import (
    CategoryViewSet,
    ClothingItemViewSet,
    RentalOrderViewSet,
    PaymentViewSet,
    RazorpayWebhookView,
)

router = DefaultRouter()
router.register(r"categories", CategoryViewSet, basename="category")
router.register(r"items", ClothingItemViewSet, basename="item")
router.register(r"orders", RentalOrderViewSet, basename="order")

# First define the router.urls
urlpatterns = router.urls

# Then extend it with additional manual paths
payment_create = PaymentViewSet.as_view({'post': 'create_razorpay_order'})
urlpatterns += [
    path('payment/create/', payment_create, name='create-razorpay-order'),
    path('payment/webhook/', RazorpayWebhookView.as_view(), name='razorpay-webhook'),
]
