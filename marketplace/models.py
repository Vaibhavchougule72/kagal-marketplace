from django.db import models
from django.utils import timezone
from datetime import timedelta
from django.contrib.auth.models import User
from cloudinary.models import CloudinaryField

from PIL import Image
from io import BytesIO
from django.core.files.base import ContentFile
import cloudinary.uploader
import os


def optimize_and_upload(image_field, folder_name):
    img = Image.open(image_field)
    img = img.convert("RGB")

    # Resize main image
    img.thumbnail((600, 600))

    buffer = BytesIO()
    img.save(buffer, format="WEBP", quality=60, optimize=True)
    buffer.seek(0)

    file_name = os.path.splitext(image_field.name)[0]

    result = cloudinary.uploader.upload(
        ContentFile(buffer.read()),
        public_id=file_name,
        folder=folder_name,
        overwrite=True,
        resource_type="image",
        format="webp",
        quality="auto",
        fetch_format="webp",
        eager=[
            {"width": 300, "crop": "scale", "quality": "auto", "fetch_format": "webp"},
            {"width": 150, "crop": "scale", "quality": "auto", "fetch_format": "webp"}
        ]
    )

    return result['public_id']

class Category(models.Model):
    name = models.CharField(max_length=200)
    image = CloudinaryField('image', blank=True, null=True)

    def save(self, *args, **kwargs):
        if self.image:
            public_id = optimize_and_upload(self.image, "categories")
            self.image = public_id

        super().save(*args, **kwargs)

    def __str__(self):
        return self.name

class Store(models.Model):
    name = models.CharField(max_length=200)
    category = models.ForeignKey("Category", on_delete=models.CASCADE)
    image = CloudinaryField('image', blank=True, null=True)
    description = models.TextField(blank=True)

    commission_percent = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        default=10,
        help_text="Platform commission percentage"
    )

    def __str__(self):
        return self.name
    
from django.db import models
from cloudinary.models import CloudinaryField
from PIL import Image
from io import BytesIO
from django.core.files.base import ContentFile
import cloudinary.uploader
import os

class Product(models.Model):
    name = models.CharField(max_length=200)
    store = models.ForeignKey("Store", on_delete=models.CASCADE)
    category = models.ForeignKey("Category", on_delete=models.CASCADE)

    price = models.DecimalField(max_digits=10, decimal_places=2)
    image = CloudinaryField('image', blank=True, null=True)
    description = models.TextField(blank=True)

    is_featured = models.BooleanField(default=False)
    is_active = models.BooleanField(default=True)
    upi_only = models.BooleanField(default=False)

    def save(self, *args, **kwargs):
        if self.image:
            public_id = optimize_and_upload(self.image, "products")
            self.image = public_id

        super().save(*args, **kwargs)

    def __str__(self):
        return self.name

class Order(models.Model):

    STATUS_CHOICES = [
        ('REQUEST_SUBMITTED', 'Request Submitted'),
        ('ACCEPTED', 'Accepted'),
        ('PICKED_UP', 'Picked Up'),
        ('OUT_FOR_DELIVERY', 'Out For Delivery'),
        ('DELIVERED', 'Delivered'),
        ('FAILED', 'Failed'),
        ('CANCELLED', 'Cancelled'),
    ]

    PAYMENT_CHOICES = [
        ('COD', 'Cash on Delivery'),
        ('UPI', 'UPI'),
    ]

    store = models.ForeignKey(Store, on_delete=models.CASCADE)

    customer_name = models.CharField(max_length=200)
    phone = models.CharField(max_length=10, db_index=True)
    address = models.TextField()

    latitude = models.FloatField(null=True, blank=True)
    longitude = models.FloatField(null=True, blank=True)

    subtotal = models.DecimalField(max_digits=10, decimal_places=2)
    delivery_fee = models.DecimalField(max_digits=10, decimal_places=2)
    small_order_fee = models.DecimalField(max_digits=10, decimal_places=2)

    discount = models.DecimalField(max_digits=10, decimal_places=2, default=0)

    coupon_code = models.CharField(max_length=20, null=True, blank=True)
    total = models.DecimalField(max_digits=10, decimal_places=2)

    payment_method = models.CharField(max_length=10, choices=PAYMENT_CHOICES)

    payment_id = models.CharField(max_length=200, null=True, blank=True)
    refund_id = models.CharField(max_length=200, null=True, blank=True)
    refund_amount = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    is_refunded = models.BooleanField(default=False)

    status = models.CharField(max_length=30, choices=STATUS_CHOICES, default='REQUEST_SUBMITTED', db_index=True)

    created_at = models.DateTimeField(auto_now_add=True,db_index=True)

    assigned_delivery = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='delivery_orders'
    )

    accepted_at = models.DateTimeField(null=True, blank=True)
    picked_at = models.DateTimeField(null=True, blank=True)
    out_for_delivery_at = models.DateTimeField(null=True, blank=True)
    delivered_at = models.DateTimeField(null=True, blank=True)

    delivery_otp = models.CharField(max_length=6, blank=True, null=True)
    delivery_otp_sent_at = models.DateTimeField(blank=True, null=True)

    delivery_partner_phone = models.CharField(max_length=10, blank=True, null=True, db_index=True)

    delivery_distance = models.FloatField(null=True, blank=True)
    delivery_time_minutes = models.IntegerField(null=True, blank=True)
    delivery_payout = models.DecimalField(max_digits=6, decimal_places=2, default=0)

    def __str__(self):
        return f"Order #{self.id} - {self.customer_name}"
        
    from django.utils import timezone

    def save(self, *args, **kwargs):

        if self.status == "ACCEPTED" and not self.accepted_at:
            self.accepted_at = timezone.now()

        if self.status == "PICKED_UP" and not self.picked_at:
            self.picked_at = timezone.now()

        if self.status == "OUT_FOR_DELIVERY" and not self.out_for_delivery_at:

            self.out_for_delivery_at = timezone.now()

        if self.status == "DELIVERED" and not self.delivered_at:
            self.delivered_at = timezone.now()

        super().save(*args, **kwargs)

from django.contrib.auth.models import User

class DeliveryPartnerProfile(models.Model):

    user = models.OneToOneField(User, on_delete=models.CASCADE)

    phone = models.CharField(max_length=10, db_index=True)
    is_available = models.BooleanField(default=True)
    is_active = models.BooleanField(default=True)

    joined_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.user.username

class OrderItem(models.Model):
    order = models.ForeignKey(Order, on_delete=models.CASCADE, related_name='items')
    product = models.ForeignKey(Product, on_delete=models.CASCADE, null=True, blank=True)
    bundle_name = models.CharField(max_length=200, null=True, blank=True)
    quantity = models.IntegerField()
    price = models.DecimalField(max_digits=10, decimal_places=2)

    def __str__(self):

        if self.product:
            return self.product.name

        return self.bundle_name or "Bundle Item"


class PendingOrder(models.Model):

    store_id = models.IntegerField()

    customer_name = models.CharField(max_length=100)
    phone = models.CharField(max_length=10, db_index=True)
    address = models.TextField()

    latitude = models.FloatField()
    longitude = models.FloatField()

    subtotal = models.DecimalField(max_digits=10, decimal_places=2)
    delivery_fee = models.DecimalField(max_digits=10, decimal_places=2)
    small_order_fee = models.DecimalField(max_digits=10, decimal_places=2)
    discount = models.DecimalField(max_digits=10, decimal_places=2, default=0)

    coupon_code = models.CharField(max_length=20, null=True, blank=True)
    total = models.DecimalField(max_digits=10, decimal_places=2)

    payment_method = models.CharField(max_length=10)

    items_snapshot = models.JSONField(default=dict)

    otp = models.CharField(max_length=6)
    otp_expiry = models.DateTimeField()
    otp_attempts = models.IntegerField(default=0)

    resend_count = models.IntegerField(default=0)

    is_payment_processed = models.BooleanField(default=False)

    created_at = models.DateTimeField(auto_now_add=True,db_index=True)

    def is_expired(self):
        return timezone.now() > self.otp_expiry

    def can_resend(self):
        return timezone.now() > self.created_at + timedelta(seconds=30)

    def __str__(self):
        return f"PendingOrder #{self.id}"
    
class Bundle(models.Model):
    name = models.CharField(max_length=200)
    store = models.ForeignKey("Store", on_delete=models.CASCADE)
    description = models.TextField(blank=True)
    price = models.DecimalField(max_digits=8, decimal_places=2)
    image = CloudinaryField('image', blank=True, null=True)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)

    def save(self, *args, **kwargs):
        if self.image:
            public_id = optimize_and_upload(self.image, "bundles")
            self.image = public_id

        super().save(*args, **kwargs)

    def __str__(self):
        return self.name


class BundleItem(models.Model):

    bundle = models.ForeignKey(Bundle, on_delete=models.CASCADE, related_name="items")

    product = models.ForeignKey(Product, on_delete=models.CASCADE)

    quantity = models.IntegerField(default=1)

    def __str__(self):
        return f"{self.bundle.name} - {self.product.name}"
    

class CustomerRisk(models.Model):

    phone = models.CharField(max_length=10, unique=True)

    successful_orders = models.IntegerField(default=0)
    cancelled_orders = models.IntegerField(default=0)
    refused_orders = models.IntegerField(default=0)

    cod_blocked = models.BooleanField(default=False)

    updated_at = models.DateTimeField(auto_now=True)

    def total_bad_orders(self):
        return self.cancelled_orders + self.refused_orders

    def __str__(self):
        return self.phone
    

class Coupon(models.Model):

    code = models.CharField(max_length=20, unique=True)

    description = models.CharField(max_length=200, blank=True)

    discount_type = models.CharField(
        max_length=10,
        choices=[
            ("PERCENT", "Percent"),
            ("FLAT", "Flat")
        ]
    )

    discount_value = models.DecimalField(max_digits=6, decimal_places=2)

    min_order_value = models.DecimalField(max_digits=10, decimal_places=2, default=0)

    max_discount = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)

    usage_limit = models.IntegerField(default=1)

    used_count = models.IntegerField(default=0)

    valid_from = models.DateTimeField()

    valid_to = models.DateTimeField()

    is_active = models.BooleanField(default=True)

    created_at = models.DateTimeField(auto_now_add=True, db_index=True)

    def __str__(self):
        return self.code
    
class CouponUsage(models.Model):

    coupon = models.ForeignKey(Coupon, on_delete=models.CASCADE)

    phone = models.CharField(max_length=10, db_index=True)

    used_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ("coupon", "phone")

    def __str__(self):
        return f"{self.phone} - {self.coupon.code}"
    
