from rest_framework import serializers
from .models import Category, ClothingItem, RentalOrder

class CategorySerializer(serializers.ModelSerializer):
    class Meta:
        model = Category
        fields = ["id","name","slug"]

class ClothingItemSerializer(serializers.ModelSerializer):
    category = CategorySerializer(read_only=True)
    category_id = serializers.PrimaryKeyRelatedField(
        queryset=Category.objects.all(), write_only=True, source="category"
    )

    class Meta:
        model = ClothingItem
        fields = [
            "id","name","description","image","daily_rate","available",
            "category","category_id"
        ]

class RentalOrderSerializer(serializers.ModelSerializer):
    user       = serializers.ReadOnlyField(source="user.id")
    item       = ClothingItemSerializer(read_only=True)
    item_id    = serializers.PrimaryKeyRelatedField(
                    queryset=ClothingItem.objects.filter(available=True),
                    write_only=True, source="item"
                )

    class Meta:
        model = RentalOrder
        fields = [
            "id","user","item","item_id",
            "start_date","end_date","total_price","status","created_at",
        ]

    def create(self, validated_data):
        # attach request user
        validated_data["user"] = self.context["request"].user
        return super().create(validated_data)
