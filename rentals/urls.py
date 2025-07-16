from rest_framework.routers import DefaultRouter
from .views import CategoryViewSet, ClothingItemViewSet, RentalOrderViewSet

router = DefaultRouter()
router.register(r"categories", CategoryViewSet, basename="category")
router.register(r"items",      ClothingItemViewSet, basename="item")
router.register(r"orders",     RentalOrderViewSet, basename="order")

urlpatterns = router.urls