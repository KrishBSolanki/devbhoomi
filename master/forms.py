from django import forms

from hotels.models import Amenity, Hotel, RoomType


class BaseStyledModelForm(forms.ModelForm):
    """Apply Bootstrap/Tailwind-friendly classes to all widgets."""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for name, field in self.fields.items():
            if isinstance(field.widget, forms.CheckboxInput):
                field.widget.attrs.update({"class": "form-check-input accent-peach"})
            elif isinstance(field.widget, forms.CheckboxSelectMultiple):
                field.widget.attrs.update({"class": "amenity-multiselect space-y-2"})
            elif isinstance(field.widget, (forms.FileInput, forms.ClearableFileInput)):
                field.widget.attrs.update({
                    "class": "form-control form-control-dark file-input",
                })
            else:
                field.widget.attrs.update({
                    "class": "form-control form-control-dark",
                })
            # Expose an easy-to-use span value for templates without custom tags
            field.span = field.widget.attrs.get("data-span", "2")


class HotelForm(BaseStyledModelForm):
    class Meta:
        model = Hotel
        fields = [
            "name",
            "slug",
            "city",
            "property_type",
            "description",
            "address",
            "distance_from_temple",
            "landmark",
            "latitude",
            "longitude",
            "base_price",
            "discount_percentage",
            "rating",
            "star_rating",
            "total_reviews",
            "amenities",
            "has_temple_view",
            "has_free_cancellation",
            "has_breakfast",
            "has_parking",
            "has_wifi",
            "has_ac",
            "is_active",
            "is_featured",
            "badge",
            "main_image",
        ]
        widgets = {
            "description": forms.Textarea(attrs={"rows": 4}),
            "address": forms.Textarea(attrs={"rows": 3}),
            "amenities": forms.SelectMultiple(attrs={"class": "form-select select-multi"}),
        }


class RoomTypeForm(BaseStyledModelForm):
    amenities = forms.ModelMultipleChoiceField(
        queryset=Amenity.objects.all(),
        required=False,
        widget=forms.CheckboxSelectMultiple,
    )

    class Meta:
        model = RoomType
        fields = [
            "name",
            "slug",
            "bed_type",
            "capacity",
            "max_guests",
            "price_per_night",
            "size_sqft",
            "total_rooms",
            "description",
            "amenities",
            "image",
            "is_available",
        ]
        widgets = {
            "description": forms.Textarea(attrs={"rows": 3}),
            "slug": forms.TextInput(attrs={"placeholder": "auto-generated if blank"}),
        }


class AmenityForm(BaseStyledModelForm):
    class Meta:
        model = Amenity
        fields = ["name", "icon", "category"]
