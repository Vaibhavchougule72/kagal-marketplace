from django import forms

class ProductUploadForm(forms.Form):
    excel_file = forms.FileField()