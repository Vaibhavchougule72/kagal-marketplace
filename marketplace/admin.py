from django.contrib import admin
from .models import Category, Store, Product, Order, OrderItem
from django.urls import path
from django.utils.html import format_html
from .views import generate_delivery_pdf, generate_store_pdf
from django.urls import reverse
from .models import StoreTiming, StoreHoliday


@admin.register(Category)
class CategoryAdmin(admin.ModelAdmin):
    list_display = ('name',)

class StoreTimingInline(admin.TabularInline):
    model = StoreTiming
    extra = 1

class StoreHolidayInline(admin.TabularInline):
    model = StoreHoliday
    extra = 1
    
@admin.register(Store)
class StoreAdmin(admin.ModelAdmin):
    list_display = ('name', 'category', 'commission_percent')
    list_filter = ('category',)
    inlines = [StoreTimingInline, StoreHolidayInline]


from django.contrib import admin
from django.urls import path, reverse
from django.utils.html import format_html
from django.http import HttpResponse
from django.shortcuts import render, redirect
from django.contrib import messages

import pandas as pd
import traceback
import logging

from .views import generate_delivery_pdf, generate_store_pdf
from .forms import ProductUploadForm

from .models import (
    Category,
    Store,
    Product,
    Order,
    OrderItem,
    StoreTiming,
    StoreHoliday,
    Bundle,
    BundleItem,
    Coupon,
    DeliveryPartnerProfile
)

logger = logging.getLogger(__name__)

from django.core.files import File
import os

@admin.register(Product)
class ProductAdmin(admin.ModelAdmin):

    list_display = ('name', 'store', 'price', 'is_active', 'upi_only')
    list_filter = ('store', 'is_active')
    search_fields = ('name',)

    def get_urls(self):
        urls = super().get_urls()

        custom_urls = [
            path(
                'bulk-upload/',
                self.admin_site.admin_view(self.bulk_upload),
                name='product_bulk_upload'
            ),
        ]

        return custom_urls + urls

    def bulk_upload(self, request):

        try:

            if request.method == "POST":

                form = ProductUploadForm(
                    request.POST,
                    request.FILES
                )

                if form.is_valid():

                    file = request.FILES["excel_file"]

                    df = pd.read_excel(file)

                    count = 0

                    for index, row in df.iterrows():

                        try:

                            store = Store.objects.get(
                                name=str(row["store"]).strip()
                            )

                            category = Category.objects.get(
                                name=str(row["category"]).strip()
                            )

                            product = Product(
                                name=str(row["name"]).strip(),
                                store=store,
                                category=category,
                                price=row["price"],
                                description=str(row.get("description", "")).strip(),
                                is_featured=row["is_featured"],
                                is_active=row["is_active"],
                                upi_only=row["upi_only"]
                            )

                            image_path = str(row.get("image_path", "")).strip()

                            if image_path:

                                filename = os.path.basename(image_path)

                                if os.path.exists(image_path):

                                    with open(image_path, "rb") as f:
                                        product.image.save(filename, File(f), save=False)

                                else:
                                    raise Exception(f"Image not found: {image_path}")

                            product.save()

                            count += 1

                        except Exception as row_error:

                            logger.exception(
                                f"ROW ERROR row {index+2}"
                            )

                            return HttpResponse(
                                f"<h2>Row Error {index+2}</h2><pre>{row_error}</pre>",
                                status=500
                            )

                    self.message_user(
                        request,
                        f"{count} products uploaded successfully."
                    )

                    return redirect("../")

            else:
                form = ProductUploadForm()

            return render(
                request,
                "admin/bulk_upload_products.html",
                {"form": form}
            )

        except Exception:

            logger.exception("MAIN BULK UPLOAD ERROR")

            return HttpResponse(
                f"<pre>{traceback.format_exc()}</pre>",
                status=500
            )
from django.contrib import admin
from django.urls import path, reverse
from django.utils.html import format_html
from django.http import HttpResponse
import traceback

from .models import Order, OrderItem


class OrderItemInline(admin.TabularInline):
    model = OrderItem
    extra = 0


@admin.register(Order)
class OrderAdmin(admin.ModelAdmin):

    inlines = [OrderItemInline]

    list_display = (
        "id",
        "store",
        "customer_name",
        "phone",
        "total",
        "status",
        "payment_method",
        "created_at",
        "pdf_buttons",   # ✅ ADD THIS
    )

    list_filter = ("status", "payment_method", "created_at")
    search_fields = ("customer_name", "phone", "id")
    readonly_fields = ("created_at", "pdf_buttons")

    fieldsets = (
        ("Customer Info", {
            "fields": (
                "store",
                "customer_name",
                "phone",
                "address",
                "latitude",
                "longitude",
            )
        }),

        ("Payment Info", {
            "fields": (
                "subtotal",
                "delivery_fee",
                "handling_fee",
                "total",
                "payment_method",
                "payment_id",
            )
        }),

        ("Order Status", {
            "fields": (
                "status",
                "assigned_delivery",
                "accepted_at",
                "picked_at",
                "out_for_delivery_at",
                "delivered_at",
            )
        }),

        ("System Info", {
            "fields": ("created_at", "pdf_buttons")
        }),

        
    )

    # 🔥 CRITICAL DEBUG PART
    def get_queryset(self, request):
        try:
            qs = super().get_queryset(request)

            # Force DB query (important)
            list(qs[:2])

            return qs

        except Exception as e:
            print("🔥 QUERY ERROR:", str(e))
            print(traceback.format_exc())
            return Order.objects.none()

    def changelist_view(self, request, extra_context=None):
        try:
            return super().changelist_view(request, extra_context)

        except Exception as e:
            error_trace = traceback.format_exc()

            return HttpResponse(
                f"""
                <h1 style='color:red;'>🔥 ADMIN LIST ERROR</h1>
                <pre>{error_trace}</pre>
                """,
                content_type="text/html"
            )

    def change_view(self, request, object_id, form_url='', extra_context=None):
        try:
            return super().change_view(request, object_id, form_url, extra_context)

        except Exception as e:
            error_trace = traceback.format_exc()

            return HttpResponse(
                f"""
                <h1 style='color:red;'>🔥 ORDER DETAIL ERROR</h1>
                <pre>{error_trace}</pre>
                """,
                content_type="text/html"
            )
    def get_urls(self):
        urls = super().get_urls()
        custom_urls = [
            path(
                '<int:order_id>/delivery-pdf/',
                self.admin_site.admin_view(generate_delivery_pdf),
                name='order-delivery-pdf',
            ),
            path(
                '<int:order_id>/store-pdf/',
                self.admin_site.admin_view(generate_store_pdf),
                name='order-store-pdf',
            ),
        ]
        return custom_urls + urls

    def pdf_buttons(self, obj):
        delivery_url = reverse("admin:order-delivery-pdf", args=[obj.id])
        store_url = reverse("admin:order-store-pdf", args=[obj.id])

        return format_html(
            '<a class="button" href="{}">Delivery PDF</a>&nbsp;'
            '<a class="button" href="{}">Store PDF</a>',
            delivery_url,
            store_url,
        )
    
    def send_otp_button(self, obj):

        url = reverse("send_delivery_otp", args=[obj.id])

        return format_html(
            '<a class="button" href="{}">Send Delivery OTP</a>',
            url
        )

    send_otp_button.short_description = "Delivery OTP"

    pdf_buttons.short_description = "Download PDFs"

    def save_model(self, request, obj, form, change):

        if obj.status == "DELIVERED":

            from .views import calculate_distance

            if obj.latitude and obj.longitude:

                BUS_STAND_LAT = 16.5775
                BUS_STAND_LON = 74.3169

                distance = calculate_distance(
                    obj.latitude,
                    obj.longitude,
                    BUS_STAND_LAT,
                    BUS_STAND_LON
                )

                obj.delivery_distance = round(distance, 2)

            if obj.accepted_at and obj.delivered_at:

                minutes = (
                    obj.delivered_at - obj.accepted_at
                ).total_seconds() / 60

                obj.delivery_time_minutes = int(minutes)

            # Payment rule
            d = obj.delivery_distance or 0

            if d <= 2:
                obj.delivery_payout = 15
            elif d <= 3:
                obj.delivery_payout = 18
            elif d <= 4:
                obj.delivery_payout = 22
            else:
                obj.delivery_payout = 25

        super().save_model(request, obj, form, change)

from .models import Bundle, BundleItem

class BundleItemInline(admin.TabularInline):
    model = BundleItem
    extra = 1


@admin.register(Bundle)
class BundleAdmin(admin.ModelAdmin):
    inlines = [BundleItemInline]

from .models import Coupon

admin.site.register(Coupon)

from .models import DeliveryPartnerProfile

admin.site.register(DeliveryPartnerProfile)