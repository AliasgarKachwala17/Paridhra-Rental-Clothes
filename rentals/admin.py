from django.contrib import admin
from .models import Category, ClothingItem, RentalOrder

admin.site.register(Category)
admin.site.register(ClothingItem)
admin.site.register(RentalOrder)