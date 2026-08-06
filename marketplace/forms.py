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

        widgets = {

            "severity": forms.RadioSelect(),

            "category": forms.RadioSelect(),

            "subcategory": forms.Select(attrs={
                "class": "form-select"
            }),

            "description": forms.Textarea(attrs={
                "rows": 5,
                "placeholder": "Describe the issue..."
            }),
        }