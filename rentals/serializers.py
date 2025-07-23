from rest_framework import serializers
from .models import Category, ClothingItem, ClothingItemImage, RentalOrder

class CategorySerializer(serializers.ModelSerializer):
    class Meta:
        model  = Category
        fields = "__all__"

class ClothingItemImageSerializer(serializers.ModelSerializer):
    class Meta:
        model  = ClothingItemImage
        fields = ("id","image")

class ClothingItemSerializer(serializers.ModelSerializer):
    images      = ClothingItemImageSerializer(many=True, read_only=True)
    image_files = serializers.ListField(
        child=serializers.ImageField(),
        write_only=True,
        required=False,
        help_text="Upload one or more images"
    )
    class Meta:
        model  = ClothingItem
        fields = (
            "id","name","description","category","sizes",
            "daily_rate","available","images","image_files",
        )

    def create(self, validated_data):
        files = validated_data.pop("image_files", [])
        item  = super().create(validated_data)
        for f in files:
            ClothingItemImage.objects.create(item=item, image=f)
        return item

    def update(self, instance, validated_data):
        files = validated_data.pop("image_files", [])
        item  = super().update(instance, validated_data)
        for f in files:
            ClothingItemImage.objects.create(item=item, image=f)
        return item

class RentalOrderSerializer(serializers.ModelSerializer):
    total_price = serializers.DecimalField(max_digits=10, decimal_places=2, read_only=True)

    class Meta:
        model  = RentalOrder
        fields = (
            "id", "item", "size", "start_date", "end_date",
            "total_price", "status", "created_at"
        )
        read_only_fields = ("id", "total_price", "created_at")

    def validate(self, data):
        # 1) size must be one of item.sizes
        item = data["item"]
        if data["size"] not in item.sizes:
            raise serializers.ValidationError({"size": "Invalid size for this item"})
        # 2) end_date must be after start_date
        if data["end_date"] < data["start_date"]:
            raise serializers.ValidationError("`end_date` must not be before `start_date`")
        return data

    def create(self, validated_data):
        # tie the order to the logged‑in user
        validated_data["user"] = self.context["request"].user
        return super().create(validated_data)