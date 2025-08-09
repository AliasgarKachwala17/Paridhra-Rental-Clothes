# rentals/views.py
from rest_framework.parsers import MultiPartParser, FormParser
from .models import Category, ClothingItem, RentalOrder, SubCategory
from .serializers import CategorySerializer, ClothingItemSerializer, RentalOrderSerializer, SubCategorySerializer
from drf_spectacular.utils import extend_schema
import razorpay
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework import status, viewsets, permissions
from drf_spectacular.utils import extend_schema, OpenApiExample, OpenApiTypes
from rest_framework import serializers
import hmac
import hashlib
from rest_framework.views import APIView
from django.conf import settings


class CategoryViewSet(viewsets.ReadOnlyModelViewSet):
    serializer_class = CategorySerializer

    def get_queryset(self):
        # parent categories only
        return Category.objects.filter(parent__isnull=True)

class SubCategoryViewSet(viewsets.ReadOnlyModelViewSet):
    serializer_class = CategorySerializer

    def get_queryset(self):
        return Category.objects.filter(parent__isnull=False)


class ClothingItemViewSet(viewsets.ModelViewSet):
    queryset         = ClothingItem.objects.all()
    serializer_class = ClothingItemSerializer
    permission_classes = [permissions.AllowAny]
    parser_classes     = [MultiPartParser, FormParser]

@extend_schema(request=RentalOrderSerializer)
class RentalOrderViewSet(viewsets.ModelViewSet):
    queryset         = RentalOrder.objects.all()
    serializer_class = RentalOrderSerializer
    permission_classes = [permissions.IsAuthenticated]


class PaymentRequestSerializer(serializers.Serializer):
    order_id = serializers.IntegerField()
    name = serializers.CharField()
    email = serializers.EmailField()
    phone = serializers.CharField()
    address = serializers.CharField()

class PaymentViewSet(viewsets.ViewSet):
    permission_classes = [permissions.IsAuthenticated]

    @extend_schema(request=PaymentRequestSerializer)
    @action(methods=['post'], detail=False, url_path='create_razorpay_order')
    def create_razorpay_order(self, request):
        data = request.data
        order_id = data.get('order_id')

        try:
            order = RentalOrder.objects.get(id=order_id, user=request.user)
        except RentalOrder.DoesNotExist:
            return Response({"error": "Order not found."}, status=404)

        # Save user info
        order.name = data.get("name")
        order.email = data.get("email")
        order.phone = data.get("phone")
        order.address = data.get("address")
        order.save()

        # Only allow payment for pending orders
        if order.status != "pending":
            return Response({"error": "This order cannot be paid."}, status=400)

        client = razorpay.Client(auth=(settings.RAZORPAY_KEY_ID, settings.RAZORPAY_KEY_SECRET))
        razorpay_order = client.order.create({
            "amount": int(float(order.total_price) * 100),  # paise
            "currency": "INR",
            "payment_capture": 1,
            "notes": {
                "rental_order_id": str(order.id),
                "user_email": request.user.email,
            }
        })
        # Optionally store razorpay_order['id'] in your RentalOrder model
        order.payment_id = razorpay_order['id']
        order.save(update_fields=["payment_id"])
        return Response({
            "razorpay_order_id": razorpay_order["id"],
            "razorpay_key": settings.RAZORPAY_KEY_ID,
            "amount": razorpay_order["amount"],
            "currency": razorpay_order["currency"],
            "order": RentalOrderSerializer(order).data,
        })

class RazorpayWebhookPayloadSerializer(serializers.Serializer):
    event = serializers.CharField()
    payload = serializers.DictField()

from rest_framework.views import APIView

class RazorpayWebhookView(APIView):
    permission_classes = [permissions.AllowAny]

    @extend_schema(request=RazorpayWebhookPayloadSerializer)
    def post(self, request, *args, **kwargs):
        if not settings.DEBUG:  # Only verify signature in production
            webhook_secret = "your_actual_webhook_secret"
            received_sig = request.META.get('HTTP_X_RAZORPAY_SIGNATURE')
            if not received_sig:
                return Response({"error": "Missing Razorpay signature"}, status=400)

            body = request.body
            generated_sig = hmac.new(webhook_secret.encode(), body, hashlib.sha256).hexdigest()
            if not hmac.compare_digest(received_sig, generated_sig):
                return Response({"error": "Invalid signature"}, status=400)



        # Proceed to process payment
        event = request.data.get("event")
        payload = request.data.get("payload", {})
        if event == "payment.captured":
            razorpay_order_id = payload["payment"]["entity"]["order_id"]
            try:
                order = RentalOrder.objects.get(payment_id=razorpay_order_id)
                order.status = "active"
                order.save()
            except RentalOrder.DoesNotExist:
                return Response({"error": "Order not found for this payment."}, status=404)
        return Response({"status": "ok"})    