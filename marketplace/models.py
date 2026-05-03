from django.db import models
from django.utils import timezone
from datetime import timedelta
from django.contrib.auth.models import User
from cloudinary.models import CloudinaryField
from decimal import Decimal


class Category(models.Model):
    name = models.CharField(max_length=200)
    image = CloudinaryField('image', blank=True, null=True)

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


    def is_open(self):
        now = timezone.localtime()
        today = now.date()
        current_time = now.time()
        weekday = now.weekday()

        # 🔴 Holiday check
        if self.storeholiday_set.filter(date=today).exists():
            return False

        # 🟢 Get all timings for today
        timings = self.timings.filter(day=weekday, is_closed=False)

        for timing in timings:

            # ✅ Normal case
            if timing.open_time < timing.close_time:
                if timing.open_time <= current_time <= timing.close_time:
                    return True

            # ✅ Midnight crossing case
            else:
                if current_time >= timing.open_time or current_time <= timing.close_time:
                    return True

        return False

    def get_next_open_time(self):
        now = timezone.localtime()
        weekday = now.weekday()
        current_time = now.time()

        for i in range(7):
            day = (weekday + i) % 7

            timings = self.timings.filter(day=day, is_closed=False).order_by("open_time")

            for timing in timings:
                # ✅ Same day → check future time only
                if i == 0:
                    if current_time < timing.open_time:
                        return timing.open_time.strftime("%I:%M %p")
                else:
                    return timing.open_time.strftime("%I:%M %p")

        return "Closed"

    @property
    def next_open_time(self):
        return self.get_next_open_time()
    def __str__(self):
        return self.name

class Product(models.Model):
    name = models.CharField(max_length=200)
    store = models.ForeignKey("Store", on_delete=models.CASCADE)
    category = models.ForeignKey("Category", on_delete=models.CASCADE)

    price = models.DecimalField(max_digits=10, decimal_places=2)
     # ✅ HERO SETTINGS
    is_hero = models.BooleanField(default=False)
    offer_text = models.CharField(max_length=100, blank=True, null=True)

    discount_price = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        blank=True,
        null=True
    )
    
    hero_priority = models.IntegerField(default=0)

    image = CloudinaryField('image', blank=True, null=True)
    description = models.TextField(blank=True)

    is_featured = models.BooleanField(default=False)

    is_active = models.BooleanField(default=True)

    upi_only = models.BooleanField(
        default=False,
        help_text="If enabled, this product allows only UPI payment"
    )

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
    handling_fee = models.DecimalField(max_digits=10, decimal_places=2, default=0)
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
    rider_latitude = models.FloatField(null=True, blank=True)
    rider_longitude = models.FloatField(null=True, blank=True)

    def __str__(self):
        return f"Order #{self.id} - {self.customer_name}"
        
    from django.utils import timezone

    def save(self, *args, **kwargs):

        from .views import calculate_distance  # import here to avoid circular import
        import math

        # -------------------------
        # STATUS TIMESTAMPS
        # -------------------------
        if self.status == "ACCEPTED" and not self.accepted_at:
            self.accepted_at = timezone.now()

        if self.status == "PICKED_UP" and not self.picked_at:
            self.picked_at = timezone.now()

        if self.status == "OUT_FOR_DELIVERY" and not self.out_for_delivery_at:
            self.out_for_delivery_at = timezone.now()

        if self.status == "DELIVERED" and not self.delivered_at:
            self.delivered_at = timezone.now()

        # ==================================================
        # 🔥 DELIVERY METRICS CALCULATION (MAIN LOGIC)
        # ==================================================
        if self.status == "DELIVERED":

            try:
                # 📍 Store location (YOU MUST ADD THESE FIELDS IF NOT EXISTS)
                store_lat = 16.579644   # fallback (bus stand)
                store_lon = 74.312721

                # If you later add store lat/lon → replace above

                # 📏 distance
                raw_distance = calculate_distance(
                    store_lat,
                    store_lon,
                    self.latitude,
                    self.longitude
                )
                if raw_distance <= 1:
                    distance = raw_distance
                else:
                    distance = raw_distance * 1.55

                # ⏱ time
                time_minutes = int(distance * 5)

                # 💰 payout formula
                # 💰 NEW RIDER PAYOUT LOGIC
                payout = 12 + (distance * 3.5)

                # round to nearest rupee
                payout = round(payout)

                # minimum guarantee
                payout = max(payout, 15)

                # SAVE
                self.delivery_distance = round(distance, 2)
                self.delivery_time_minutes = time_minutes
                self.delivery_payout = round(payout, 2)

            except Exception as e:
                print("DELIVERY CALCULATION ERROR:", e)

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
    handling_fee = models.DecimalField(max_digits=10, decimal_places=2, default=0)
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
    razorpay_order_id = models.CharField(
        max_length=120,
        blank=True,
        null=True,
        db_index=True
    )
    
    from django.utils import timezone

    def is_expired(self):
        if not self.otp_expiry:
            return True
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

    created_at = models.DateTimeField(auto_now_add=True,db_index=True)

    def original_price(self):
        total = Decimal(0)

        for item in self.items.all():
            total += item.product.price * item.quantity

        return total
    def savings(self):
        return int(self.original_price() - self.price)

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
    

class StoreTiming(models.Model):

    DAYS = [
        (0, "Monday"),
        (1, "Tuesday"),
        (2, "Wednesday"),
        (3, "Thursday"),
        (4, "Friday"),
        (5, "Saturday"),
        (6, "Sunday"),
    ]

    store = models.ForeignKey("Store", on_delete=models.CASCADE, related_name="timings")

    day = models.IntegerField(choices=DAYS)

    open_time = models.TimeField()
    close_time = models.TimeField()

    is_closed = models.BooleanField(default=False)

    def __str__(self):
        return f"{self.store.name} - {self.get_day_display()}"
    
class StoreHoliday(models.Model):

    store = models.ForeignKey("Store", on_delete=models.CASCADE)

    date = models.DateField()

    reason = models.CharField(max_length=200, blank=True)

    def __str__(self):
        return f"{self.store.name} - {self.date}"
    
