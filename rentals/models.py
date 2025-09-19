from django.db import models
from django.contrib.auth import get_user_model

User = get_user_model()

class Category(models.Model):
    name = models.CharField(max_length=100, unique=True)
    slug = models.SlugField(unique=True)
    image = models.ImageField(upload_to="category_images/", null=True, blank=True)

    def __str__(self): return self.name

class SubCategory(models.Model):
    category = models.ForeignKey(Category, related_name="subcategories", on_delete=models.CASCADE)
    name = models.CharField(max_length=100)
    slug = models.SlugField(unique=True)
    image = models.ImageField(upload_to="subcategory_images/", null=True, blank=True)

    def __str__(self): return f"{self.name} ({self.category.name})"

SIZE_CHOICES = [
    ("XS", "Extra Small"),
    ("S", "Small"),
    ("M", "Medium"),
    ("L", "Large"),
    ("XL", "Extra Large"),
    ("XXL", "Double Extra Large"),
    ("XXXL", "Triple Extra Large"),
]
class ClothingItem(models.Model):
    category = models.ForeignKey(Category, related_name="items", on_delete=models.CASCADE, null=True, blank=True)
    subcategory = models.ForeignKey(SubCategory, related_name="items", on_delete=models.CASCADE, null=True, blank=True)
    name        = models.CharField(max_length=200)
    description = models.TextField()
    sizes       = models.JSONField(default=list,blank=True)
    
    daily_rate  = models.DecimalField(max_digits=8, decimal_places=2)
    available   = models.BooleanField(default=True)

    def __str__(self): return f"{self.name} ({self.category.name} > {self.subcategory.name if self.subcategory else 'No Sub'})"

class ClothingItemImage(models.Model):
    item  = models.ForeignKey(ClothingItem, related_name="images", on_delete=models.CASCADE)
    image = models.ImageField(upload_to="clothing_images/")

    def __str__(self):
        return f"Image for {self.item.name}"

class RentalOrder(models.Model):
    STATUS_CHOICES = [
        ("pending", "Pending"),
        ("active", "Active"),
        ("completed", "Completed"),
    ]
    status = models.CharField(max_length=10, choices=STATUS_CHOICES, default="pending")
    name = models.CharField(max_length=100, default="name")
    email = models.EmailField(default="email")
    phone = models.CharField(max_length=15, default="+91")
    address = models.TextField(default="city")
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name="orders")
    
    # 🔽 Removed single `item`
    # item = models.ForeignKey(ClothingItem, on_delete=models.PROTECT, related_name="orders")

    start_date = models.DateField()
    end_date = models.DateField()
    total_price = models.DecimalField(max_digits=10, decimal_places=2, blank=True)
    payment_id = models.CharField(max_length=100, blank=True, null=True)
    shiprocket_awb = models.CharField(max_length=50, blank=True, null=True)
    shiprocket_shipment_id = models.CharField(max_length=50, blank=True, null=True)
    shipment_id = models.CharField(max_length=50, blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)
    # 🔄 reverse / return shipping
    return_shipment_id = models.CharField(max_length=50, blank=True, null=True)
    return_awb = models.CharField(max_length=50, blank=True, null=True)

    def save(self, *args, **kwargs):
        # 1) compute days (+1 so same-day rent counts as 1 day)
        days = (self.end_date - self.start_date).days + 1

        # 2) compute total = sum of each item daily_rate * qty * days
        total = sum([
            item.item.daily_rate * item.quantity * days
            for item in self.items.all()
        ]) if self.pk else 0  # only calculate if order exists
        self.total_price = total
        super().save(*args, **kwargs)

    def __str__(self):
        return f"Order #{self.id} - {self.user.email} ({self.start_date} to {self.end_date})"


class RentalOrderItem(models.Model):
    order = models.ForeignKey(RentalOrder, related_name="items", on_delete=models.CASCADE)
    item = models.ForeignKey(ClothingItem, on_delete=models.PROTECT)
    size = models.CharField(max_length=10, default="M")
    quantity = models.PositiveIntegerField(default=1)

    def __str__(self):
        return f"{self.item.name} (x{self.quantity})"