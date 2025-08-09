from rest_framework import serializers
from .models import Category, ClothingItem, ClothingItemImage, RentalOrder, SubCategory
from django.db.models import Q
from datetime import timedelta

class CategorySerializer(serializers.ModelSerializer):
    class Meta:
        model = Category
        fields = "__all__"

class SubCategorySerializer(serializers.ModelSerializer):
    category_slug = serializers.CharField(source="category.slug", read_only=True)
    category_name = serializers.CharField(source="category.name", read_only=True)

    class Meta:
        model = SubCategory
        fields = (
            "id", "name", "slug", "image",
            "category",       # existing FK field (id)
            "category_name",  # readable name
            "category_slug"   # readable slug
        )


class ClothingItemImageSerializer(serializers.ModelSerializer):
    class Meta:
        model  = ClothingItemImage
        fields = ("id","image")

class ClothingItemSerializer(serializers.ModelSerializer):
    images = ClothingItemImageSerializer(many=True, read_only=True)
    image_files = serializers.ListField(
        child=serializers.ImageField(),
        write_only=True,
        required=False,
        help_text="Upload one or more images"
    )
    category = CategorySerializer(read_only=True)
    subcategory = SubCategorySerializer(read_only=True)
    
    # ✅ Fixed these lines
    category_id = serializers.PrimaryKeyRelatedField(
        queryset=Category.objects.all(),
        source='category',
        write_only=True
    )
    subcategory_id = serializers.PrimaryKeyRelatedField(
        queryset=SubCategory.objects.all(),
        source='subcategory',
        write_only=True,
        required=False
    )

    class Meta:
        model = ClothingItem
        fields = (
            "id", "name", "description", "category", "subcategory",
            "category_id", "subcategory_id", "sizes", "daily_rate",
            "available", "images", "image_files"
        )

    def create(self, validated_data):
        files = validated_data.pop("image_files", [])
        item = super().create(validated_data)
        for f in files:
            ClothingItemImage.objects.create(item=item, image=f)
        return item

    def update(self, instance, validated_data):
        files = validated_data.pop("image_files", [])
        item = super().update(instance, validated_data)
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
        item = data["item"]
        start_date = data["start_date"]
        end_date = data["end_date"]
        size = data["size"]

        # Validate size exists in item's size list
        if size not in item.sizes:
            raise serializers.ValidationError({"size": "Invalid size for this item"})

        if end_date < start_date:
            raise serializers.ValidationError("`end_date` must not be before `start_date`")

        overlapping_orders = RentalOrder.objects.filter(
            item=item,
            status__in=["pending", "active"],
        ).filter(
            Q(start_date__lte=end_date) & Q(end_date__gte=start_date)
        )

        if overlapping_orders.exists():
            raise serializers.ValidationError("This item is already rented during the selected dates.")

        return data

    def create(self, validated_data):
        validated_data["user"] = self.context["request"].user
        return super().create(validated_data)




        