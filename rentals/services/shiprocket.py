# rentals/services/shiprocket.py
import requests
from django.conf import settings

class ShiprocketAPI:
    def __init__(self):
        self.base_url = settings.SHIPROCKET_BASE_URL
        self.token = self.get_token()

    def get_token(self):
        url = f"{self.base_url}/auth/login"
        payload = {
            "email": settings.SHIPROCKET_EMAIL.strip(),
            "password": settings.SHIPROCKET_PASSWORD,
        }
        res = requests.post(url, json=payload)
        res.raise_for_status()
        return res.json()["token"]

    def create_order(self, order):
        url = f"{self.base_url}/orders/create/adhoc"
        headers = {"Authorization": f"Bearer {self.token}"}

        # ✅ Multi-item order support
        order_items = [
            {
                "name": oi.item.name,
                "sku": str(oi.item.id),
                "units": oi.quantity,
                "selling_price": str(oi.item.daily_rate),
            }
            for oi in order.items.all()
        ]

        payload = {
            "order_id": str(order.id),
            "order_date": str(order.created_at.date()),
            "pickup_location": "warehouse",
            "billing_customer_name": order.name,
            "billing_last_name": "",
            "billing_address": order.address,
            "billing_city": "Pune",
            "billing_pincode": "411042",
            "billing_state": "Maharashtra",
            "billing_country": "India",
            "billing_email": order.email,
            "billing_phone": order.phone,
            "shipping_is_billing": True,
            "order_items": order_items,
            "payment_method": "Prepaid",
            "sub_total": str(order.total_price),
            "length": 10,
            "breadth": 10,
            "height": 1,
            "weight": 0.5
        }
        res = requests.post(url, json=payload, headers=headers)
        res.raise_for_status()
        return res.json()

    def track_order(self, shipment_id):
        url = f"{self.base_url}/courier/track/shipment/{shipment_id}"
        headers = {"Authorization": f"Bearer {self.token}"}
        r = requests.get(url, headers=headers)
        r.raise_for_status()
        return r.json()
