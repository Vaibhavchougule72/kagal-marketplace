from django import forms

class ProductUploadForm(forms.Form):
    excel_file = forms.FileField()

from django import forms
from .models import Complaint


class ComplaintForm(forms.ModelForm):

    photo = forms.ImageField(
        required=False
    )

    class Meta:
        model = Complaint

        fields = [
            "severity",
            "category",
            "subcategory",
            "description",
        ]

    def clean_description(self):
        description = self.cleaned_data.get("description", "").strip()

        if len(description) < 20:
            raise forms.ValidationError(
                "Please describe the issue in at least 20 characters."
            )

        return description

    def clean_subcategory(self):
        category = self.cleaned_data.get("category")
        subcategory = self.cleaned_data.get("subcategory", "").strip()

        allowed_subcategories = {

            "PORTAL": [
                "Payment Issue",
                "Coupon Issue",
                "App Crash",
                "Login Issue",
                "Wrong Price",
                "Other",
            ],

            "FOOD_QUALITY": [
                "Taste",
                "Freshness",
                "Undercooked",
                "Overcooked",
                "Bad Smell",
                "Foreign Object",
                "Other",
            ],

            "DELIVERED_FOOD": [
                "Packaging Damaged",
                "Food Spilled",
                "Missing Items",
                "Wrong Order",
                "Seal Broken",
                "Quantity Less",
                "Other",
            ],

            "DELIVERY_SERVICE": [
                "Late Delivery",
                "Delivery Partner Behaviour",
                "Couldn't Contact Rider",
                "Wrong Address Attempt",
                "Other",
            ],
        }

        if category not in allowed_subcategories:
            raise forms.ValidationError(
                "Please select a valid issue category."
            )

        if subcategory not in allowed_subcategories[category]:
            raise forms.ValidationError(
                "Please select a valid issue."
            )

        return subcategory

    def clean_photo(self):
        photo = self.cleaned_data.get("photo")

        if not photo:
            return photo

        # 5 MB maximum
        if photo.size > 5 * 1024 * 1024:
            raise forms.ValidationError(
                "Photo must be smaller than 5 MB."
            )

        return photo