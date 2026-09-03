from django.db import models
from django.utils import timezone
from datetime import timedelta
from django.contrib.auth.models import User
from cloudinary.models import CloudinaryField
from decimal import Decimal
from .firebase import send_push_notification
from firebase_admin import messaging

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

    average_rating = models.FloatField(
        default=0
    )

    total_ratings = models.IntegerField(
        default=0
    )

    is_featured = models.BooleanField(
        default=False,
        verbose_name="Featured Store"
    )

    featured_priority = models.IntegerField(default=0)


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

    unavailable_10_12 = models.BooleanField(
        default=False,
        help_text="Hide product from 10 AM - 12 PM"
    )

    unavailable_12_3 = models.BooleanField(
        default=False,
        help_text="Hide product from 12 PM - 3 PM"
    )

    unavailable_3_630 = models.BooleanField(
        default=False,
        help_text="Hide product from 3 PM - 6:30 PM"
    )

    unavailable_630_9 = models.BooleanField(
        default=False,
        help_text="Hide product from 6:30 PM - 9 PM"
    )

    from django.utils import timezone

    from django.utils import timezone

    def is_available_now(self):
        now = timezone.localtime()
        current_minutes = now.hour * 60 + now.minute

        # 10:00 AM - 12:00 PM
        if 10 * 60 <= current_minutes < 12 * 60:
            return not self.unavailable_10_12

        # 12:00 PM - 3:00 PM
        if 12 * 60 <= current_minutes < 15 * 60:
            return not self.unavailable_12_3

        # 3:00 PM - 6:30 PM
        if 15 * 60 <= current_minutes < 18 * 60 + 30:
            return not self.unavailable_3_630

        # 6:30 PM - 9:00 PM
        if 18 * 60 + 30 <= current_minutes < 21 * 60:
            return not self.unavailable_630_9

        # Outside product availability schedule
        return True

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

    customer_note = models.TextField(
        blank=True,
        null=True,
        max_length=500
    )

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

        old_status = None

        if self.pk:

            try:

                old_status = Order.objects.get(pk=self.pk).status

            except Order.DoesNotExist:

                pass

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
        # ==================================================
        # PUSH NOTIFICATIONS
        # ==================================================

        if old_status != self.status:

            title = ""
            body = ""

            # -----------------------------------
            # ORDER ACCEPTED
            # -----------------------------------
            if self.status == "ACCEPTED":

                title = "Order Accepted ✅"

                body = (
                    f"Your order has been accepted by restaurant."
                )

            # -----------------------------------
            # PICKED UP
            # -----------------------------------
            elif self.status == "PICKED_UP":

                title = "Order In Progress 🛵"

                body = (
                    f"Your order is being prepared."
                )

            # -----------------------------------
            # OUT FOR DELIVERY
            # -----------------------------------
            elif self.status == "OUT_FOR_DELIVERY":

                title = "Out for Delivery 🚚"

                body = (
                    f"Rider is on the way with your order."
                )

            # -----------------------------------
            # DELIVERED
            # -----------------------------------
            elif self.status == "DELIVERED":

                title = "Order Delivered 🎉"

                body = (
                    f"Your order was delivered successfully."
                )

            # -----------------------------------
            # SEND PUSH
            # -----------------------------------
            if title:

                devices = DeviceToken.objects.filter(
                    phone=self.phone
                )

                for device in devices:

                    try:

                        send_push_notification(
                            device.token,
                            title,
                            body
                        )

                    except messaging.UnregisteredError:

                        print(
                            "🗑 Removing invalid FCM token:",
                            device.id
                        )

                        device.delete()

                    except Exception as e:

                        print(
                            "❌ Push Notification Error:",
                            str(e)
                        )

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

    order = models.ForeignKey(
        Order,
        on_delete=models.CASCADE,
        related_name='items'
    )

    product = models.ForeignKey(
        Product,
        on_delete=models.SET_NULL,
        null=True,
        blank=True
    )

    # ✅ ADD THIS
    bundle = models.ForeignKey(
        "Bundle",
        on_delete=models.SET_NULL,
        null=True,
        blank=True
    )

    bundle_name = models.CharField(
        max_length=200,
        null=True,
        blank=True
    )

    quantity = models.IntegerField()

    # customer paid price
    price = models.DecimalField(
        max_digits=10,
        decimal_places=2
    )

    # actual store price
    original_price = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        null=True,
        blank=True
    )

    # platform discount
    discount_amount = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        default=0
    )

    def __str__(self):

        if self.product:
            return self.product.name

        if self.bundle:
            return self.bundle.name

        return self.bundle_name or "Bundle Item"
    
    @property
    def display_name(self):

        if self.product:
            return self.product.name

        if self.bundle:
            return self.bundle.name

        return self.bundle_name or "Unknown Item"
    def __str__(self):

        return self.display_name
    def save(self, *args, **kwargs):

        if self.bundle and not self.bundle_name:
            self.bundle_name = self.bundle.name

        super().save(*args, **kwargs)

import uuid
class PendingOrder(models.Model):

    store_id = models.IntegerField()

    customer_name = models.CharField(max_length=100)
    phone = models.CharField(max_length=10, db_index=True)
    address = models.TextField()

    customer_note = models.TextField(
        blank=True,
        null=True,
        max_length=500
    )

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

    otp = models.CharField(max_length=128)
    otp_expiry = models.DateTimeField()
    otp_attempts = models.IntegerField(default=0)

    resend_count = models.IntegerField(default=0)

    is_payment_processing = models.BooleanField(default=False)

    is_payment_processed = models.BooleanField(default=False)
    created_order = models.ForeignKey(
        "Order",
        on_delete=models.SET_NULL,
        null=True,
        blank=True
    )

    payment_id = models.CharField(
        max_length=200,
        null=True,
        blank=True
    )

    razorpay_order_id = models.CharField(
        max_length=200,
        blank=True,
        null=True
    )

    cart_data = models.JSONField(
        default=dict
    )

    is_completed = models.BooleanField(
        default=False
    )

    created_at = models.DateTimeField(auto_now_add=True,db_index=True)
    updated_at = models.DateTimeField(auto_now=True)

    payment_token = models.UUIDField(
        default=uuid.uuid4,
        unique=True,
        null=True,
        blank=True
    )

    payment_token_expires_at = models.DateTimeField(
        null=True,
        blank=True
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

    created_at = models.DateTimeField(auto_now_add=True)

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
    
class Banner(models.Model):
    title = models.CharField(max_length=100)
    subtitle = models.CharField(max_length=200, blank=True, null=True)

    image = CloudinaryField(
        'image',
        blank=True,
        null=True
    )
    product = models.ForeignKey(Product, null=True, blank=True, on_delete=models.SET_NULL)
    bundle = models.ForeignKey(
        Bundle,
        on_delete=models.SET_NULL,
        null=True,
        blank=True
    )
    button_text = models.CharField(max_length=50, default="Order Now")
    button_link = models.CharField(max_length=200, blank=True, null=True)

    is_active = models.BooleanField(default=True)
    is_popup = models.BooleanField(default=False)

    priority = models.IntegerField(default=0)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return self.title
    def clean(self):

        from django.core.exceptions import ValidationError

        if self.product and self.bundle:
            raise ValidationError(
                "Select either product OR bundle."
            )

        if not self.product and not self.bundle:
            raise ValidationError(
                "Select at least one product or bundle."
            )
        
class StoreRating(models.Model):

    order = models.OneToOneField(
        Order,
        on_delete=models.CASCADE
    )

    store = models.ForeignKey(
        Store,
        on_delete=models.CASCADE,
        related_name="ratings"
    )

    customer_phone = models.CharField(
        max_length=10
    )

    rating = models.IntegerField()

    comment = models.TextField(
        blank=True,
        null=True
    )

    created_at = models.DateTimeField(
        auto_now_add=True
    )

    def __str__(self):
        return f"{self.store.name} - {self.rating}"
    
from django.db import models
from django.contrib.auth.models import User

class DeviceToken(models.Model):

    user = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        null=True,
        blank=True
    )

    # ✅ CUSTOMER PHONE
    phone = models.CharField(
        max_length=10,
        null=True,
        blank=True,
        db_index=True
    )

    token = models.TextField(
        unique=True
    )

    created_at = models.DateTimeField(
        auto_now_add=True
    )

    updated_at = models.DateTimeField(
        auto_now=True
    )

    def __str__(self):

        return f"{self.phone} - {self.token[:20]}"
    

class CheckoutLead(models.Model):

    name = models.CharField(
        max_length=200,
        blank=True,
        null=True
    )

    phone = models.CharField(
        max_length=10,
        db_index=True
    )

    address = models.TextField(
        blank=True,
        null=True
    )

    last_cart_value = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        default=0
    )

    last_payment_method = models.CharField(
        max_length=20,
        blank=True,
        null=True
    )

    last_store = models.ForeignKey(
        Store,
        on_delete=models.SET_NULL,
        null=True,
        blank=True
    )

    checkout_attempts = models.IntegerField(
        default=1
    )

    created_at = models.DateTimeField(
        auto_now_add=True
    )

    updated_at = models.DateTimeField(
        auto_now=True
    )

    def __str__(self):
        return f"{self.phone} - {self.name}"
    

class Expense(models.Model):

    reason = models.CharField(
        max_length=255
    )

    amount = models.DecimalField(
        max_digits=10,
        decimal_places=2
    )

    payment_method = models.CharField(
        max_length=100,
        blank=True,
        null=True
    )

    notes = models.TextField(
        blank=True,
        null=True
    )

    created_at = models.DateTimeField(
        auto_now_add=True
    )

    def __str__(self):
        return f"{self.reason} - ₹{self.amount}"
    

class OfferSlider(models.Model):

    title = models.CharField(
        max_length=200,
        blank=True,
        null=True
    )

    image = CloudinaryField(
        'image'
    )

    link = models.CharField(
        max_length=500,
        blank=True,
        null=True,
        help_text="Example: /store/1/ OR /category/2/"
    )

    is_active = models.BooleanField(
        default=True
    )

    priority = models.IntegerField(
        default=0
    )

    created_at = models.DateTimeField(
        auto_now_add=True
    )

    class Meta:
        ordering = ["priority"]

    def __str__(self):
        return self.title or f"Offer {self.id}"



from django.contrib.auth.models import User


class NotificationCampaign(models.Model):

    AUDIENCE_CHOICES = [
        ("all", "All Customers"),
        ("new", "New Customers"),
        ("repeat", "Repeat Customers"),
        ("inactive", "Inactive Customers"),
        ("phone", "Specific Customer"),
    ]

    STATUS_CHOICES = [
        ("sending", "Sending"),
        ("completed", "Completed"),
        ("failed", "Failed"),
    ]

    title = models.CharField(
        max_length=100
    )

    message = models.TextField()

    audience = models.CharField(
        max_length=20,
        choices=AUDIENCE_CHOICES
    )

    phone = models.CharField(
        max_length=10,
        blank=True,
        null=True
    )

    high_priority = models.BooleanField(
        default=False
    )

    save_history = models.BooleanField(
        default=True
    )

    status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default="completed"
    )

    total_recipients = models.PositiveIntegerField(
        default=0
    )

    successful = models.PositiveIntegerField(
        default=0
    )

    failed = models.PositiveIntegerField(
        default=0
    )

    created_by = models.ForeignKey(
        User,
        null=True,
        blank=True,
        on_delete=models.SET_NULL
    )

    created_at = models.DateTimeField(
        auto_now_add=True,
        db_index=True
    )

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.title} ({self.created_at:%d %b %Y})"


class Complaint(models.Model):

    SEVERITY_CHOICES = [
        ("LOW", "Low"),
        ("MEDIUM", "Medium"),
        ("HIGH", "High"),
        ("CRITICAL", "Critical"),
    ]

    CATEGORY_CHOICES = [
        ("PORTAL", "Portal / App"),
        ("FOOD_QUALITY", "Food Quality"),
        ("DELIVERED_FOOD", "Delivered Food Condition"),
        ("DELIVERY_SERVICE", "Delivery Service"),
    ]

    STATUS_CHOICES = [
        ("NEW", "New"),
        ("UNDER_REVIEW", "Under Review"),
        ("WAITING_RESTAURANT", "Waiting for Restaurant"),
        ("WAITING_DELIVERY", "Waiting for Delivery Partner"),
        ("RESOLVED", "Resolved"),
        ("CLOSED", "Closed"),
        ("REJECTED", "Rejected"),
    ]

    order = models.OneToOneField(
        Order,
        on_delete=models.CASCADE,
        related_name="complaint"
    )

    store = models.ForeignKey(
        Store,
        on_delete=models.CASCADE,
        related_name="complaints"
    )

    customer_name = models.CharField(max_length=200)

    phone = models.CharField(
        max_length=10,
        db_index=True
    )

    delivery_partner = models.ForeignKey(
        User,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="delivery_complaints"
    )

    severity = models.CharField(
        max_length=20,
        choices=SEVERITY_CHOICES
    )

    category = models.CharField(
        max_length=30,
        choices=CATEGORY_CHOICES
    )

    subcategory = models.CharField(max_length=100)

    description = models.TextField()

    status = models.CharField(
        max_length=30,
        choices=STATUS_CHOICES,
        default="NEW",
        db_index=True
    )

    resolution_note = models.TextField(blank=True)

    internal_note = models.TextField(blank=True)

    refund_amount = models.DecimalField(
        max_digits=8,
        decimal_places=2,
        default=0
    )

    coupon_code = models.CharField(
        max_length=30,
        blank=True
    )

    created_at = models.DateTimeField(
        auto_now_add=True,
        db_index=True
    )

    updated_at = models.DateTimeField(
        auto_now=True
    )

    resolved_at = models.DateTimeField(
        null=True,
        blank=True
    )

    @property
    
    def complaint_number(self):
        if self.created_at:
            return f"CMP-{self.created_at:%Y%m%d}-{self.id:05d}"
        return f"CMP-{self.id:05d}"

    def __str__(self):
        return self.complaint_number

class ComplaintPhoto(models.Model):

    complaint = models.ForeignKey(
        Complaint,
        related_name="photos",
        on_delete=models.CASCADE
    )

    image = CloudinaryField("image")

    uploaded_at = models.DateTimeField(
        auto_now_add=True
    )

    def __str__(self):
        return f"{self.complaint.complaint_number}"

from django.db import models
from django.utils import timezone

class Customer(models.Model):

    GENDER_CHOICES = [
        ("MALE", "Male"),
        ("FEMALE", "Female"),
        ("OTHER", "Other"),
        ("PREFER_NOT_TO_SAY", "Prefer not to say"),
    ]

    phone = models.CharField(
        max_length=10,
        unique=True,
        db_index=True
    )

    name = models.CharField(
        max_length=150,
        blank=True,
        default=""
    )

    email = models.EmailField(
        blank=True,
        default=""
    )

    gender = models.CharField(
        max_length=20,
        choices=GENDER_CHOICES,
        blank=True,
        null=True
    )

    date_of_birth = models.DateField(
        blank=True,
        null=True
    )

    is_active = models.BooleanField(
        default=True
    )

    is_verified = models.BooleanField(
        default=False
    )

    last_login_at = models.DateTimeField(
        null=True,
        blank=True
    )

    created_at = models.DateTimeField(
        auto_now_add=True
    )

    updated_at = models.DateTimeField(
        auto_now=True
    )

    def __str__(self):
        return f"{self.name or 'Customer'} - {self.phone}"

class CustomerOTP(models.Model):
    phone = models.CharField(
        max_length=10,
        db_index=True
    )

    otp = models.CharField(
        max_length=128
    )

    purpose = models.CharField(
        max_length=30,
        choices=[
            ("LOGIN", "Login"),
            ("REGISTER", "Register"),
            ("RESET", "Reset"),
        ],
        default="LOGIN"
    )

    attempts = models.PositiveIntegerField(
        default=0
    )

    resend_count = models.PositiveIntegerField(
        default=0
    )

    created_at = models.DateTimeField(
        auto_now_add=True
    )

    expires_at = models.DateTimeField()

    verified_at = models.DateTimeField(
        null=True,
        blank=True
    )

    is_used = models.BooleanField(
        default=False
    )

    def is_expired(self):
        return timezone.now() >= self.expires_at

    def __str__(self):
        return f"{self.phone} - {self.purpose}"