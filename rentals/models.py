from django.db import models
from django.contrib.auth import get_user_model

User = get_user_model()

class Category(models.Model):
    name = models.CharField(max_length=100, unique=True)
    slug = models.SlugField(unique=True)

    def __str__(self): return self.name

class ClothingItem(models.Model):
    category = models.ForeignKey(Category, related_name="items", on_delete=models.CASCADE)
    name        = models.CharField(max_length=200)
    description = models.TextField()
    image       = models.ImageField(upload_to="items/", blank=True, null=True)
    daily_rate  = models.DecimalField(max_digits=8, decimal_places=2)
    available   = models.BooleanField(default=True)

    def __str__(self): return f"{self.name} ({self.category.name})"

class RentalOrder(models.Model):
    STATUS_CHOICES = [
        ("pending",   "Pending"),
        ("active",    "Active"),
        ("completed", "Completed"),
    ]

    user        = models.ForeignKey(User, on_delete=models.CASCADE, related_name="orders")
    item        = models.ForeignKey(ClothingItem, on_delete=models.PROTECT, related_name="orders")
    start_date  = models.DateField()
    end_date    = models.DateField()
    total_price = models.DecimalField(max_digits=10, decimal_places=2, blank=True)
    status      = models.CharField(max_length=10, choices=STATUS_CHOICES, default="pending")
    created_at  = models.DateTimeField(auto_now_add=True)

    def save(self, *args, **kwargs):
        # Calculate total and mark item unavailable
        days = (self.end_date - self.start_date).days + 1
        self.total_price = days * self.item.daily_rate
        super().save(*args, **kwargs)
        # lock the item
        if self.status in ("pending","active"):
            self.item.available = False
            self.item.save()
        elif self.status == "completed":
            self.item.available = True
            self.item.save()

    def __str__(self):
        return f"Order #{self.id} by {self.user}"
