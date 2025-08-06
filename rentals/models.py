from django.db import models
from django.contrib.auth import get_user_model

User = get_user_model()

class Category(models.Model):
    name = models.CharField(max_length=100, unique=True)
    slug = models.SlugField(unique=True)
    parent = models.ForeignKey("self", null=True, blank=True, on_delete=models.CASCADE, related_name="subcategories")
    image = models.ImageField(
        upload_to="category_images/",
        null=True, blank=True,
        
    )

    def __str__(self): 
        return self.name

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
    category = models.ForeignKey(Category, related_name="items", on_delete=models.CASCADE)
    name        = models.CharField(max_length=200)
    description = models.TextField()
    sizes       = models.JSONField(default=list,blank=True)
    
    daily_rate  = models.DecimalField(max_digits=8, decimal_places=2)
    available   = models.BooleanField(default=True)

    def __str__(self): return f"{self.name} ({self.category.name})"


class ClothingItemImage(models.Model):
    item  = models.ForeignKey(ClothingItem, related_name="images", on_delete=models.CASCADE)
    image = models.ImageField(upload_to="clothing_images/")

    def __str__(self):
        return f"Image for {self.item.name}"

class RentalOrder(models.Model):
    STATUS_CHOICES = [
        ("pending",   "Pending"),
        ("active",    "Active"),
        ("completed", "Completed"),
    ]
    name = models.CharField(max_length=100,default="name")
    email = models.EmailField(default="email")
    phone = models.CharField(max_length=15, default="+91")
    address = models.TextField(default="city")
    user        = models.ForeignKey(User, on_delete=models.CASCADE, related_name="orders")
    item        = models.ForeignKey(ClothingItem, on_delete=models.PROTECT, related_name="orders")
    size        = models.CharField(max_length=10,default="M")
    start_date  = models.DateField()
    end_date    = models.DateField()
    total_price = models.DecimalField(max_digits=10, decimal_places=2, blank=True)
    payment_id = models.CharField(max_length=100, blank=True, null=True)
    status      = models.CharField(max_length=10, choices=STATUS_CHOICES, default="pending")
    created_at  = models.DateTimeField(auto_now_add=True)

    def save(self, *args, **kwargs):
        # 1) compute days (+1 so same‑day rent counts as 1 day)
        days = (self.end_date - self.start_date).days + 1
        # 2) compute total
        self.total_price = days * self.item.daily_rate
        super().save(*args, **kwargs)

        # 3) update availability
        if self.status in ("pending", "active"):
            self.item.available = False
        else:  # completed
            self.item.available = True
        self.item.save()

    def __str__(self):
        return f"{self.item} - {self.user} ({self.start_date} to {self.end_date})"