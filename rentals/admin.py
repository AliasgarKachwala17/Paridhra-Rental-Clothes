# rentals/admin.py
from django import forms
from django.contrib import admin
from .models import Category, SubCategory, ClothingItem, ClothingItemImage, RentalOrder, SIZE_CHOICES

@admin.register(Category)
class CategoryAdmin(admin.ModelAdmin):
    list_display = ("id", "name", "slug", "image")

@admin.register(SubCategory)
class SubCategoryAdmin(admin.ModelAdmin):
    list_display = ("id", "name", "slug", "category", "image")


class ClothingItemImageInline(admin.TabularInline):  # or admin.StackedInline
    model = ClothingItemImage
    extra = 1  # Number of empty forms to display
    fields = ("image",)

@admin.register(ClothingItem)
class ClothingItemAdmin(admin.ModelAdmin):
    list_display = ('name', 'category', 'subcategory', 'available', 'daily_rate')
    list_filter = ('available', 'category', 'subcategory')
    search_fields = ('name',)
    inlines = [ClothingItemImageInline]
    

    def formfield_for_dbfield(self, db_field, **kwargs):
        from django import forms
        if db_field.name == 'sizes':
            return forms.MultipleChoiceField(
                choices=SIZE_CHOICES,
                widget=forms.CheckboxSelectMultiple,
                required=False,
                label="Available Sizes"
            )
        return super().formfield_for_dbfield(db_field, **kwargs)
        

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