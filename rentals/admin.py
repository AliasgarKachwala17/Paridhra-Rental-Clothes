# rentals/admin.py
from django import forms
from django.contrib import admin
from .models import Category, ClothingItem, ClothingItemImage, RentalOrder

class ClothingItemImageInline(admin.TabularInline):
    model = ClothingItemImage
    extra = 1

@admin.register(ClothingItem)
class ClothingItemAdmin(admin.ModelAdmin):
    list_display = ("id", "name", "category", "daily_rate", "available")
    inlines     = (ClothingItemImageInline,)

@admin.register(Category)
class CategoryAdmin(admin.ModelAdmin):
    list_display = ("id","name","slug","image")

@admin.register(ClothingItemImage)
class ClothingItemImageAdmin(admin.ModelAdmin):
    list_display = ("id","item","image")

class RentalOrderForm(forms.ModelForm):
    size = forms.ChoiceField(choices=[])  # placeholder

    class Meta:
        model  = RentalOrder
        fields = "__all__"

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        # figure out which item is selected
        item = None
        if self.instance and self.instance.pk:
            item = self.instance.item
        else:
            item_id = self.data.get("item") or self.initial.get("item")
            if item_id:
                try:
                    item = ClothingItem.objects.get(pk=item_id)
                except ClothingItem.DoesNotExist:
                    pass

        if item:
            self.fields["size"].choices = [(s, s) for s in item.sizes]
        else:
            # no item yet → no choices
            self.fields["size"].choices = []

@admin.register(RentalOrder)
class RentalOrderAdmin(admin.ModelAdmin):
    form = RentalOrderForm
    list_display = ("id","user","item","size","start_date","end_date","status")