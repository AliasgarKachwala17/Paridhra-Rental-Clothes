# rentals/views.py
from rest_framework import viewsets, permissions
from rest_framework.parsers import MultiPartParser, FormParser
from .models import Category, ClothingItem, RentalOrder
from .serializers import CategorySerializer, ClothingItemSerializer, RentalOrderSerializer
from drf_spectacular.utils import extend_schema


class CategoryViewSet(viewsets.ReadOnlyModelViewSet):
    queryset         = Category.objects.all()
    serializer_class = CategorySerializer

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
