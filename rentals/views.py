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
from django.core.mail import send_mail
import requests


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
    serializer_class = RentalOrderSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        user = self.request.user
        if user.is_staff:  # ✅ Admin/staff users can see all orders
            return RentalOrder.objects.all()
        return RentalOrder.objects.filter(user=user)  # ✅ Normal users only see their own

    @action(detail=True, methods=["get"], url_path="track")
    def track_order(self, request, pk: int = None):
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

        # update contact info
        for field in ["name","email","phone","address"]:
            setattr(order, field, data.get(field))
        order.save()

        if order.status != "pending":
            return Response({"error": "This order cannot be paid."}, status=400)

        # ✅ total_price already = rental + security deposit
        amount_paise = int(float(order.total_price) * 100)

        # ✅ Calculate total security deposit from items
        security_deposit_total = sum(
            item.item.security_deposit * item.quantity
            for item in order.items.all()
        )

        client = razorpay.Client(auth=(settings.RAZORPAY_KEY_ID, settings.RAZORPAY_KEY_SECRET))
        razorpay_order = client.order.create({
            "amount": amount_paise,
            "currency": "INR",
            "payment_capture": 1,
            "notes": {
                "rental_order_id": str(order.id),
                "security_deposit": str(security_deposit_total),  # ✅ FIXED
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
        event = request.data.get("event")
        payload = request.data.get("payload", {})

        if event == "payment.captured":
            razorpay_order_id = (
                payload.get("payment", {}).get("entity", {}).get("order_id")
                or payload.get("order_id")
            )
            try:
                order = RentalOrder.objects.get(payment_id=razorpay_order_id)
                order.status = "active"
                order.save(update_fields=["status"])

                # ✅ Create shipment
                try:
                    ship_api = ShiprocketAPI()
                    shipment = ship_api.create_order(order)

                    order.shipment_id = str(shipment.get("order_id"))
                    order.shiprocket_shipment_id = str(shipment.get("shipment_id"))
                    order.shiprocket_awb = shipment.get("awb_code", "")
                    order.save(update_fields=["shipment_id", "shiprocket_shipment_id", "shiprocket_awb"])
                except Exception as e:
                    return Response({"warning": "Payment captured, but shipment creation failed", "error": str(e)})

                # # 🔄 Immediately schedule reverse pickup
                # return_ship = ship_api.create_return_order(order)
                # order.return_shipment_id = str(return_ship.get("shipment_id"))
                # order.return_awb = return_ship.get("awb_code", "")
                # order.save(update_fields=["return_shipment_id","return_awb"])

                # ✅ Tracking link
                tracking_url = f"https://shiprocket.co/tracking/{order.shiprocket_awb}"

                # ✅ Send Email
                send_mail(
                    subject="Your Rental Order Payment is Successful ✅",
                    message=f"Hello {order.name},\n\nYour payment is confirmed.\nYour order will be placed in 3 days.\nTrack here: {tracking_url}\n\nThank you for renting with us!",
                    from_email=settings.DEFAULT_FROM_EMAIL,
                    recipient_list=[order.email],
                )
                return Response(
                    {
                        "success": True,
                        "message": "Payment captured and shipment created.",
                        "order_id": order.id,
                        "shipment_id": order.shiprocket_shipment_id,
                    },
                    status=status.HTTP_200_OK,
                )

            except RentalOrder.DoesNotExist:
                return Response({"error": "Order not found for this payment."}, status=404)
        
        # For any other event, just acknowledge
        return Response({"message": "Event ignored"}, status=status.HTTP_200_OK)


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

    @action(methods=['post'], detail=True, url_path='create-return')
    def create_return(self, request, pk=None):
        """
        Trigger a Shiprocket reverse-pickup (return) for this order.
        """
        try:
            order = RentalOrder.objects.get(pk=pk, user=request.user)
        except RentalOrder.DoesNotExist:
            return Response({"error": "Order not found"}, status=404)

        if not order.shiprocket_shipment_id:
            return Response({"error": "Forward shipment not ready yet"}, status=400)

        ship = ShiprocketAPI()
        resp = ship.create_return_order(order)

        order.return_shipment_id = resp.get("shipment_id")
        order.return_awb = resp.get("awb_code")
        order.save(update_fields=["return_shipment_id", "return_awb"])

        return Response({"return_shipment": resp})