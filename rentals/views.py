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
from .services.shiprocket import ShiprocketAPI
from datetime import datetime


class CategoryViewSet(viewsets.ReadOnlyModelViewSet):
    serializer_class = CategorySerializer
    queryset = Category.objects.all()  # ✅ No parent filtering


class SubCategoryViewSet(viewsets.ReadOnlyModelViewSet):
    serializer_class = SubCategorySerializer
    queryset = SubCategory.objects.all()  # ✅ Use SubCategory model, not Category


class ClothingItemViewSet(viewsets.ModelViewSet):
    queryset         = ClothingItem.objects.all()
    serializer_class = ClothingItemSerializer
    permission_classes = [permissions.AllowAny]
    parser_classes     = [MultiPartParser, FormParser]

@extend_schema(
    request=RentalOrderSerializer,
    responses=RentalOrderSerializer,
    description="Create and manage rental orders"
)
class RentalOrderViewSet(viewsets.ModelViewSet):
    queryset = RentalOrder.objects.all()
    serializer_class = RentalOrderSerializer
    permission_classes = [permissions.IsAuthenticated]

    @action(detail=True, methods=["get"], url_path="track")
    def track_order(self, request, pk=None):
        try:
            order = self.get_object()
            if not order.payment_id:
                return Response({"error": "Order not linked to a shipment"}, status=400)

            shipment_id = order.shipment_id  
            if not shipment_id:
                return Response({"error": "Shipment not created for this order"}, status=400)

            ship_api = ShiprocketAPI()
            tracking = ship_api.track_order(shipment_id)

            # Extract expected delivery date from tracking data
            expected_delivery = (
                tracking.get("tracking_data", {})
                .get("etd") or
                tracking.get("tracking_data", {}).get("expected_delivery")
            )

            days_left = None
            if expected_delivery:
                try:
                    delivery_date = datetime.strptime(expected_delivery, "%Y-%m-%d").date()
                    today = datetime.today().date()
                    days_left = (delivery_date - today).days
                except Exception:
                    pass

            return Response({
                "order_id": order.id,
                "shipment_id": shipment_id,
                "tracking_info": tracking,
                "days_left": days_left
            })
        except Exception as e:
            return Response({"error": str(e)}, status=500)

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

        # Save user info (for shipment later)
        order.name = data.get("name")
        order.email = data.get("email")
        order.phone = data.get("phone")
        order.address = data.get("address")
        order.save()

        # ✅ Only allow payment for pending orders
        if order.status != "pending":
            return Response({"error": "This order cannot be paid."}, status=400)

        # ✅ Recalculate total based on multiple items
        days = (order.end_date - order.start_date).days + 1
        total = sum([
            item.item.daily_rate * item.quantity * days
            for item in order.items.all()
        ])
        order.total_price = total
        order.save(update_fields=["total_price"])

        # ✅ Create Razorpay order
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

        event = request.data.get("event")
        payload = request.data.get("payload", {})

        # rentals/views.py -> inside RazorpayWebhookView.post
        if event == "payment.captured":
            razorpay_order_id = (
                payload.get("payment", {}).get("entity", {}).get("order_id")
                or payload.get("order_id")
            )

            if not razorpay_order_id:
                return Response({"error": "order_id missing in payload"}, status=400)

            try:
                order = RentalOrder.objects.get(payment_id=razorpay_order_id)
                order.status = "active"
                order.save(update_fields=["status"])

                # ✅ Create Shiprocket shipment
                ship_api = ShiprocketAPI()
                shipment = ship_api.create_order(order)

                # Shiprocket response keys:
                shiprocket_order_id = shipment.get("order_id")        # internal Shiprocket order id
                shiprocket_shipment_id = shipment.get("shipment_id")  # this is what you track
                awb_code = shipment.get("awb_code")

                order.shipment_id = str(shiprocket_order_id)  # optional, but store separately
                order.shiprocket_shipment_id = str(shiprocket_shipment_id)
                order.shiprocket_awb = awb_code or ""
                order.save(update_fields=["shipment_id", "shiprocket_shipment_id", "shiprocket_awb"])


                return Response({
                    "status": "ok",
                    "shipment": shipment
                })

            except RentalOrder.DoesNotExist:
                return Response({"error": "Order not found for this payment."}, status=404)


class ShippingViewSet(viewsets.ViewSet):
    permission_classes = [permissions.IsAuthenticated]

    @action(methods=['post'], detail=True, url_path='create-shipment')
    def create_shipment(self, request, pk=None):
        try:
            order = RentalOrder.objects.get(pk=pk, user=request.user)
        except RentalOrder.DoesNotExist:
            return Response({"error": "Order not found"}, status=404)

        shiprocket = ShiprocketAPI()
        resp = shiprocket.create_order(order)

        order.shiprocket_awb = resp["awb_code"]
        order.shiprocket_shipment_id = resp["shipment_id"]
        order.save()

        return Response({"shipment": resp})

    @action(methods=['get'], detail=True, url_path='track-shipment')
    def track_shipment(self, request, pk=None):
        try:
            order = RentalOrder.objects.get(pk=pk, user=request.user)
        except RentalOrder.DoesNotExist:
            return Response({"error": "Order not found"}, status=404)

        if not order.shiprocket_shipment_id:
            return Response({"error": "No shipment created for this order"}, status=400)

        shiprocket = ShiprocketAPI()
        resp = shiprocket.track_order(order.shiprocket_shipment_id)

        # ✅ Extract tracking data safely
        tracking_data = (
            resp.get(str(order.shiprocket_shipment_id), {})
            .get("tracking_data", {})
        )

        shipment_status = tracking_data.get("shipment_status", "Unknown")
        track_url = tracking_data.get("track_url")
        expected_delivery = (
            tracking_data.get("etd") or
            tracking_data.get("expected_delivery")
        )

        # ✅ Calculate days_left
        days_left = None
        if expected_delivery:
            from datetime import datetime
            try:
                delivery_date = datetime.strptime(expected_delivery, "%Y-%m-%d").date()
                today = datetime.today().date()
                days_left = (delivery_date - today).days
            except Exception:
                pass
        
        status_map = {
    0: "Pending Pickup",
    1: "In Transit",
    2: "Delivered",
    3: "Return to Origin Initiated",
    4: "Return to Origin Delivered",
    }

        shipment_status_code = tracking_data.get("shipment_status", 0)
        shipment_status = status_map.get(shipment_status_code, "Unknown")

        return Response({
            "order_id": order.id,
            "shipment_id": order.shiprocket_shipment_id,
            "tracking_info": {
                "tracking_data": {
                    "shipment_status": shipment_status,  # ✅ mapped to text
                    "track_url": tracking_data.get("track_url") or "Not available yet",
                    "expected_delivery": tracking_data.get("etd") or tracking_data.get("expected_delivery"),
                }
            },
            "days_left": days_left
        })