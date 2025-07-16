from rest_framework import viewsets, permissions
from .models import Category, ClothingItem, RentalOrder
from .serializers import (
    CategorySerializer,
    ClothingItemSerializer,
    RentalOrderSerializer,
)

class CategoryViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = Category.objects.all()
    serializer_class = CategorySerializer

class ClothingItemViewSet(viewsets.ModelViewSet):
    queryset         = ClothingItem.objects.all()
    serializer_class = ClothingItemSerializer
    permission_classes = [permissions.AllowAny]

class RentalOrderViewSet(viewsets.ModelViewSet):
    serializer_class   = RentalOrderSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        # only your own orders
        return RentalOrder.objects.filter(user=self.request.user)
