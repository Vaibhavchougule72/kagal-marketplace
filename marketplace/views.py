from django.shortcuts import render, get_object_or_404, redirect
from django.http import JsonResponse, HttpResponse

from django.db.models import Q
from decimal import Decimal
from django.utils import timezone
from datetime import timedelta
import random
import math
import re
from django.conf import settings
from django.contrib import messages
from .models import Category, Store, Product, Order, OrderItem, PendingOrder
from .cart import Cart
from django.contrib.auth.models import User
from .models import Bundle
from django.db.models import Count
from django.db.models import Sum
from django.db.models import F
from .models import CouponUsage
from .models import Coupon
from django.core.cache import cache
from decimal import Decimal, ROUND_HALF_UP
# from .sms_service import send_sms   ❌ comment

from decimal import Decimal, ROUND_HALF_UP

def to_paise(amount):
    return int((Decimal(amount) * 100).quantize(Decimal("1"), rounding=ROUND_HALF_UP))


def send_sms(*args, **kwargs):
    return True  # dummy function (prevents crash)

import logging
logger = logging.getLogger(__name__)
from django.db import transaction

from django.db import connection


def test_cache(request):

    cache.set("test_key", "Redis Working!", 60)

    value = cache.get("test_key")

    return HttpResponse(value)
# =====================================================
# DISTANCE CALCULATION
# =====================================================
def calculate_distance(lat1, lon1, lat2, lon2):
    R = 6371

    lat1 = math.radians(float(lat1))
    lon1 = math.radians(float(lon1))
    lat2 = math.radians(float(lat2))
    lon2 = math.radians(float(lon2))

    dlat = lat2 - lat1
    dlon = lon2 - lon1

    a = math.sin(dlat/2)**2 + math.cos(lat1) * math.cos(lat2) * math.sin(dlon/2)**2
    c = 2 * math.atan2(math.sqrt(a), math.sqrt(1-a))

    return R * c


# =====================================================
# HOME
# =====================================================
from django.core.paginator import Paginator
from django.core.cache import cache

def home(request):

    page = request.GET.get('page', 1)

    cache_key = f"home_page_{page}_{timezone.now().minute}"
    data = cache.get(cache_key)

    if not data:

        categories = Category.objects.all()
        stores = Store.objects.all()
        all_combos = Bundle.objects.filter(is_active=True)\
            .select_related('store')\
            .prefetch_related('items__product')

        # 🔥 Filter only open stores
        combos = [c for c in all_combos if c.store.is_open()][:6]

        all_products = Product.objects.filter(is_featured=True).select_related('store')
        print("TOTAL FEATURED:", all_products.count())
        featured_products_list = [
            p for p in all_products if p.store.is_open()
        ]
        print("OPEN STORES PRODUCTS:", len(featured_products_list))
        paginator = Paginator(featured_products_list, 12)  # 12 products per page
        featured_products = paginator.get_page(page)

        data = {
            "categories": categories,
            "featured_products": featured_products,
            "stores": stores,
            "combos": combos,
            "show_floating_cart": True
        }

        cache.set(cache_key, data, 300)

    return render(request, "home.html", data)

# =====================================================
# STORES
# =====================================================
def all_stores(request):
    stores = Store.objects.select_related('category').all()
    return render(request, 'all_stores.html', {'stores': stores})



def store_detail(request, store_id):

    cache_key = f"store_{store_id}"

    data = cache.get(cache_key)

    if not data:

        store = get_object_or_404(Store, id=store_id)
        products = Product.objects.filter(store=store).select_related("category", "store")
        bundles = Bundle.objects.filter(store=store, is_active=True)

        data = {
            "store": store,
            "products": products,
            "bundles": bundles,
            "show_floating_cart": True
        }

        cache.set(cache_key, data, 300)

    return render(request, "store_detail.html", data)

def add_bundle_to_cart(request, bundle_id):

    bundle = get_object_or_404(Bundle, id=bundle_id, is_active=True)

    # ✅ ADD THIS
    if not bundle.store.is_open():
        return JsonResponse({
            "success": False,
            "error": "Store is currently closed"
        })
    
    cart = request.session.get('cart', {
        'store_id': None,
        'items': {}
    })

    # Single store restriction
    if cart['store_id'] and cart['store_id'] != bundle.store.id:
        cart = {
            'store_id': bundle.store.id,
            'items': {}
        }

    cart['store_id'] = bundle.store.id

    item_key = f"bundle_{bundle.id}"

    if item_key in cart['items']:
        cart['items'][item_key]['quantity'] += 1
    else:
        cart['items'][item_key] = {
            "bundle_id": bundle.id,
            "name": bundle.name,
            "price": str(bundle.price),
            "quantity": 1,
            "is_bundle": True
        }

    request.session['cart'] = cart
    request.session.modified = True

    cart_count = sum(item['quantity'] for item in cart['items'].values())
    

    return JsonResponse({
        "success": True,
        "cart_count": cart_count
    })

# =====================================================
# CATEGORY
# =====================================================
def category_detail(request, category_id):
    return redirect('category_stores', category_id=category_id)


def category_stores(request, category_id):
    category = get_object_or_404(Category, id=category_id)
    stores = Store.objects.filter(category=category)

    return render(request, 'category_stores.html', {
        'category': category,
        'stores': stores,
        "show_floating_cart": False
    })


def category_products(request, category_id):
    category = get_object_or_404(Category, id=category_id)
    products = Product.objects.filter(category=category)

    return render(request, 'category_products.html', {
        'category': category,
        'products': products,
        "show_floating_cart": True
    })


# =====================================================
# CART
# =====================================================
def add_to_cart(request, product_id):

    product = get_object_or_404(Product, id=product_id, is_active=True)

    if not product.store.is_open():
        return JsonResponse({
            "success": False,
            "error": "Store is currently closed"
        })
    cart = request.session.get('cart', {
        'store_id': None,
        'items': {}
    })

    # single store rule
    if cart.get('store_id') and cart['store_id'] != product.store.id:
        request.session['cart'] = {
            'store_id': product.store.id,
            'items': {}
        }
        cart = request.session['cart']
    
    if not cart.get('store_id'):
        cart['store_id'] = product.store.id

    product_id = str(product.id)

    # 🔥 GET quantity from request
    try:
        qty = max(1, int(request.GET.get("qty", 1)))
    except:
        qty = 1

    if product_id in cart['items']:
        cart['items'][product_id]['quantity'] += qty
    else:
        cart['items'][product_id] = {
            'name': product.name,
            'price': str(product.price),
            'quantity': qty   # 🔥 FIX HERE
        }

    request.session['cart'] = cart
    request.session.modified = True

    cart_count = sum(item['quantity'] for item in cart['items'].values())

    return JsonResponse({
        "success": True,
        "cart_count": cart_count
    })

def decrease_cart(request, product_id):

    cart = request.session.get('cart', {'store_id': None, 'items': {}})

    # --------- PRODUCT ---------
    if product_id.isdigit():

        if product_id in cart['items']:

            cart['items'][product_id]['quantity'] -= 1

            if cart['items'][product_id]['quantity'] <= 0:
                del cart['items'][product_id]

    # --------- BUNDLE ---------
    elif product_id.startswith("bundle_"):

        if product_id in cart['items']:

            cart['items'][product_id]['quantity'] -= 1

            if cart['items'][product_id]['quantity'] <= 0:
                del cart['items'][product_id]

    request.session['cart'] = cart
    request.session.modified = True

    cart_count = sum(
        item['quantity'] for item in cart['items'].values()
    )

    return JsonResponse({
        "success": True,
        "cart_count": cart_count
    })

def remove_from_cart(request, product_id):

    cart = request.session.get('cart', {
        'store_id': None,
        'items': {}
    })

    if not cart:
        return JsonResponse({"success": False})

    if product_id in cart['items']:
        del cart['items'][product_id]

    request.session['cart'] = cart
    request.session.modified = True

    cart_count = sum(
        item['quantity'] for item in cart['items'].values()
    )

    return JsonResponse({
        'success': True,
        'cart_count': cart_count
    })
    
def view_cart(request):
    cart = request.session.get('cart', {'store_id': None, 'items': {}})
    items = []
    subtotal = Decimal(0)


    for item_id, item in cart['items'].items():

        # ======================
        # ✅ BUNDLE
        # ======================
        if item_id.startswith("bundle_"):

            try:
                bundle_id = int(item_id.split("_")[1])
                bundle = Bundle.objects.get(id=bundle_id, is_active=True)

                if not bundle.store.is_open():
                    continue

            except:
                continue

            price = Decimal(str(item.get('price', 0)))
            quantity = int(item.get('quantity', 1))

            subtotal += price * quantity

            items.append({
                "key": item_id,
                "product": None,
                "name": item["name"],
                "quantity": quantity,
                "price": price,
                "subtotal": price * quantity
            })

        # ======================
        # ✅ PRODUCT
        # ======================
        else:

            try:
                product = Product.objects.get(id=int(item_id))

                if not product.store.is_open():
                    continue

            except:
                continue

            price = Decimal(str(item.get('price', 0)))
            quantity = int(item.get('quantity', 1))

            subtotal += price * quantity

            items.append({
                "key": item_id,
                "product": product,
                "quantity": quantity,
                "price": price,
                "subtotal": price * quantity
            })

    remaining_to_149 = Decimal(149) - subtotal if subtotal < 149 else 0
    cod_not_allowed = subtotal < 149
    remaining_to_free_delivery = Decimal(499) - subtotal if subtotal < 499 else 0

    # 🔥 FIX: clear invalid cart
    if not items:
        request.session['cart'] = {'store_id': None, 'items': {}}
        request.session.modified = True

    return render(request, 'cart_partial.html', {
        'items': items,
        'subtotal': subtotal,
        'remaining_to_149': remaining_to_149,
        'cod_not_allowed': cod_not_allowed,
        'remaining_to_free_delivery': remaining_to_free_delivery,
        "show_floating_cart": False
    })


# =====================================================
# CHECKOUT + OTP
# ==================================================from django.shortcuts import render, redirect, get_object_or_404
from django.utils import timezone
from django.db import transaction
from decimal import Decimal
import random
import re
import copy
from datetime import timedelta

def checkout(request):

    PendingOrder.objects.filter(
        created_at__lt=timezone.now() - timedelta(hours=1)
    ).delete()

    cart = request.session.get('cart', {'store_id': None, 'items': {}})

    # -------------------------
    # EMPTY CART
    # -------------------------
    if not cart or not cart.get('items'):
        return redirect('home')

    # -------------------------
    # STORE RESOLUTION
    # -------------------------
    store_ids = set()

    for item_id in cart['items']:
        try:
            if item_id.isdigit():
                product = Product.objects.get(id=int(item_id))
                store_ids.add(product.store.id)

            elif item_id.startswith("bundle_"):
                bundle_id = int(item_id.split("_")[1])
                bundle = Bundle.objects.get(id=bundle_id, is_active=True)
                store_ids.add(bundle.store.id)
        except:
            continue

    if len(store_ids) != 1:
        return render(request, 'checkout.html', {
            "error": "Cart contains items from multiple stores",
            "show_floating_cart": False
        })

    store_id = list(store_ids)[0]
    store = get_object_or_404(Store, id=store_id)

    context = {
        "cart": cart,
        "store": store,
        "show_floating_cart": False,
        "simple_navbar": True,
    }

    # -------------------------
    # STORE OPEN CHECK
    # -------------------------
    if not store.is_open():
        context["error"] = f"{store.name} is currently closed"
        return render(request, "checkout.html", context)

    # -------------------------
    # CALCULATE SUBTOTAL
    # -------------------------
    subtotal = Decimal(0)
    upi_only_required = False

    for item_id, item in cart['items'].items():
        price = Decimal(str(item.get('price', 0)))
        quantity = int(item.get('quantity', 1))
        subtotal += price * quantity

        if item_id.isdigit():
            try:
                product = Product.objects.get(id=int(item_id))
                if product.upi_only:
                    upi_only_required = True
            except:
                pass

    handling_fee = Decimal(12)

    context.update({
        "subtotal": subtotal,
        "handling_fee": handling_fee,
        "upi_only_required": upi_only_required
    })

    # =========================
    # POST
    # =========================
    if request.method == "POST":
        try:
            name = request.POST.get("name")
            phone = request.POST.get("phone", "").strip()
            confirm_phone = request.POST.get("confirm_phone")
            address = request.POST.get("address")
            payment = request.POST.get("payment")
            latitude = request.POST.get("latitude")
            longitude = request.POST.get("longitude")
            coupon_code = request.POST.get("coupon_code")

            # -------------------------
            # VALIDATIONS
            # -------------------------
            if not re.match(r'^[6-9]\d{9}$', phone):
                context["error"] = "Invalid phone number"
                return render(request, "checkout.html", context)

            if not confirm_phone:
                context["error"] = "Please confirm mobile number"
                return render(request, "checkout.html", context)
            
            if not payment:
                context["error"] = "Select payment method"
                return render(request, "checkout.html", context)

            if upi_only_required and payment == "COD":
                context["error"] = "Only UPI allowed for selected items"
                return render(request, "checkout.html", context)

            if not latitude or not longitude:
                context["error"] = "Select delivery location"
                return render(request, "checkout.html", context)

            latitude = float(latitude)
            longitude = float(longitude)

            # -------------------------
            # DELIVERY
            # -------------------------
            BUS_LAT, BUS_LON = 16.5775, 74.3169
            distance = calculate_distance(latitude, longitude, BUS_LAT, BUS_LON) + 1

            if distance > 7:
                context["error"] = "Delivery not available"
                return render(request, "checkout.html", context)

            free_delivery = request.POST.get("free_delivery") == "true"

            if free_delivery:
                delivery_fee = Decimal(0)

            elif subtotal >= 499:
                delivery_fee = Decimal(0)

            else:
                delivery_fee = 20 + max(0, (distance - 2) * 5)

                delivery_fee = math.ceil(delivery_fee)   # 🔥 ALWAYS ROUND UP

                delivery_fee = min(delivery_fee, 60)

                delivery_fee = Decimal(delivery_fee)
                
            # -------------------------
            # COUPON
            # -------------------------
            discount = Decimal(0)

            if coupon_code:
                try:
                    coupon = Coupon.objects.get(code=coupon_code, is_active=True)

                    if CouponUsage.objects.filter(coupon=coupon, phone=phone).exists():
                        raise Exception("Coupon already used")

                    if subtotal < coupon.min_order_value:
                        raise Exception("Minimum order not met")

                    if coupon.discount_type == "PERCENT":
                        discount = subtotal * coupon.discount_value / 100
                        if coupon.max_discount:
                            discount = min(discount, coupon.max_discount)
                    else:
                        discount = coupon.discount_value

                except Exception as e:
                    context["error"] = str(e)
                    return render(request, "checkout.html", context)

            total = (
                Decimal(subtotal) +
                Decimal(delivery_fee) +
                Decimal(handling_fee) -
                Decimal(discount)
            )

            # ✅ ROUND PROPERLY
            total = total.quantize(Decimal("1"), rounding=ROUND_HALF_UP)
            if subtotal < 149 and payment == "COD":
                context["error"] = "COD not allowed below ₹149"
                return render(request, "checkout.html", context)

            # =========================
            # 🔵 UPI FLOW
            # =========================
            if payment == "UPI":

                import razorpay
                pending_id = request.session.get("pending_id")

                pending = None

                if pending_id:
                    try:
                        pending = PendingOrder.objects.get(id=pending_id)

                        # 🔥 IMPORTANT: check if total changed
                        if pending.total != total:
                            pending.delete()
                            pending = None

                    except PendingOrder.DoesNotExist:
                        pending = None

                if not pending:
                    pending = PendingOrder.objects.create(
                        store_id=store_id,
                        customer_name=name,
                        phone=phone,
                        address=address,
                        latitude=latitude,
                        longitude=longitude,
                        subtotal=subtotal,
                        delivery_fee=delivery_fee,
                        handling_fee=handling_fee,
                        discount=discount,
                        coupon_code=coupon_code,
                        total=total,
                        payment_method="UPI",
                        otp_expiry=timezone.now() + timedelta(minutes=5),
                        items_snapshot={
                            "store_id": store_id,
                            "items": cart["items"]
                        }
                    )
                    request.session["pending_id"] = pending.id

                client = razorpay.Client(auth=(
                        settings.RAZORPAY_KEY_ID,
                        settings.RAZORPAY_KEY_SECRET
                    ))

                amount_paise = to_paise(total)

                # 🔥 ALWAYS CREATE NEW ORDER (DO NOT REUSE)

                razorpay_order = client.order.create({
                    "amount": amount_paise,
                    "currency": "INR",
                    "payment_capture": 1
                })

                razorpay_order_id = razorpay_order["id"]

                # optional (just for debugging / reference)
                request.session["razorpay_order_id"] = razorpay_order_id
                request.session["razorpay_amount"] = amount_paise

                logger.info("=========== CHECKOUT DEBUG ===========")
                logger.info(f"TOTAL: {total}")
                logger.info(f"AMOUNT_PAISE: {amount_paise}")
                logger.info(f"RAZORPAY_ORDER_ID: {razorpay_order_id}")
                logger.info(f"PENDING_ID: {pending.id}")
                logger.info("=====================================")
                request.session["payment_data"] = {
                    "razorpay_key": settings.RAZORPAY_KEY_ID,
                    "amount": amount_paise,
                    "razorpay_order_id": razorpay_order_id,
                    "customer_name": name,
                    "phone": phone,
                    "display_amount": f"{total:.2f}",
                    "show_floating_cart": False,
                    "simple_navbar": True,
                }

                return redirect(
                    f"/upi_payment/?amount={amount_paise}"
                    f"&order_id={razorpay_order_id}"
                    f"&display_amount={total}"
                    f"&name={name}"
                    f"&phone={phone}"
                    f"&pending_id={pending.id}"
                )

            # =========================
            # 🟢 COD FLOW
            # =========================
            with transaction.atomic():

                order = Order.objects.create(
                    store_id=store_id,
                    customer_name=name,
                    phone=phone,
                    address=address,
                    latitude=latitude,
                    longitude=longitude,
                    subtotal=subtotal,
                    delivery_fee=delivery_fee,
                    handling_fee=handling_fee,
                    discount=discount,
                    coupon_code=coupon_code,
                    total=total,
                    payment_method="COD",
                    status="REQUEST_SUBMITTED"
                )

                for item_id, item in cart["items"].items():

                    if item_id.isdigit():
                        try:
                            product = Product.objects.get(id=int(item_id))

                            OrderItem.objects.create(
                                order=order,
                                product=product,
                                price=Decimal(str(item.get("price", 0))),
                                quantity=int(item.get("quantity", 1))
                            )
                        except:
                            continue

                    elif item_id.startswith("bundle_"):

                        OrderItem.objects.create(
                            order=order,
                            product=None,
                            bundle_name=item.get("name", "Combo"),
                            price=Decimal(str(item.get("price", 0))),
                            quantity=int(item.get("quantity", 1))
                        )

            request.session["cart"] = {"store_id": None, "items": {}}

            return redirect("order_success", order_id=order.id)

        except Exception as e:
            logger.error(f"CHECKOUT ERROR: {e}", exc_info=True)
            context["error"] = "Something went wrong"
            return render(request, "checkout.html", context)

    return render(request, "checkout.html", context)

# =====================================================
# VERIFY OTP
from django.shortcuts import render, get_object_or_404, redirect
from django.utils import timezone
from django.contrib import messages
from django.db import transaction
from decimal import Decimal
from datetime import timedelta
import logging

logger = logging.getLogger(__name__)

'''def verify_otp(request, pending_id):

    try:
        pending = PendingOrder.objects.filter(id=pending_id).first()

        # ❌ If not found → safe redirect (NO 500)
        if not pending:
            messages.error(request, "Session expired. Please try again.")
            return redirect("checkout")

        store = Store.objects.filter(id=pending.store_id).first()

        if not store or not store.is_open():
            return render(request, "verify_otp.html", {
                "pending_order": None,
                "error": "Store is currently closed.",
                "expiry_seconds": 0,
                "show_floating_cart": False,
                'simple_navbar': True,
            })

        # ⏳ Calculate expiry safely
        expiry_seconds = 0
        if pending.otp_expiry:
            expiry_seconds = int((pending.otp_expiry - timezone.now()).total_seconds())
            if expiry_seconds < 0:
                expiry_seconds = 0

        # -------------------------
        # OTP EXPIRED (GET)
        # -------------------------
        if pending.is_expired():
            return render(request, "verify_otp.html", {
                "pending_order": pending,
                "error": "OTP expired. Please resend OTP.",
                "expiry_seconds": 0,
                'simple_navbar': True,
                "show_floating_cart": False
            })

        # =========================
        # POST LOGIC
        # =========================
        if request.method == "POST":

            entered = request.POST.get("otp", "").strip()

            # Expiry check again
            if pending.is_expired():
                return render(request, "verify_otp.html", {
                    "pending_order": pending,
                    "error": "OTP expired. Please resend OTP.",
                    "expiry_seconds": 0,
                    'simple_navbar': True,
                    "show_floating_cart": False
                })

            # Attempts limit
            if pending.otp_attempts >= 3:
                pending.delete()
                return render(request, "verify_otp.html", {
                    "pending_order": None,
                    "error": "Too many wrong attempts. Order cancelled.",
                    "expiry_seconds": 0,
                    'simple_navbar': True,
                    "show_floating_cart": False
                })

            # OTP format validation
            if not entered.isdigit() or len(entered) != 6:
                return render(request, "verify_otp.html", {
                    "pending_order": pending,
                    "error": "Enter valid 6-digit OTP.",
                    "expiry_seconds": expiry_seconds,
                    'simple_navbar': True,
                    "show_floating_cart": False
                })

            # OTP mismatch
            if entered != pending.otp:
                pending.otp_attempts += 1
                pending.save()

                attempts_left = 3 - pending.otp_attempts

                return render(request, "verify_otp.html", {
                    "pending_order": pending,
                    "error": f"Invalid OTP. {attempts_left} attempts left.",
                    "expiry_seconds": expiry_seconds,
                    'simple_navbar': True,
                    "show_floating_cart": False
                })

            # ✅ OTP CORRECT

            cart_items = pending.items_snapshot or {}

            if not cart_items.get("items"):
                return redirect("home")

            # =========================
            # COD FLOW
            # =========================
            if pending.payment_method == "COD":

                with transaction.atomic():

                    order = Order.objects.create(
                        store_id=pending.store_id,
                        customer_name=pending.customer_name,
                        phone=pending.phone,
                        address=pending.address,
                        latitude=pending.latitude,
                        longitude=pending.longitude,
                        subtotal=pending.subtotal,
                        delivery_fee=pending.delivery_fee,
                        handling_fee=getattr(pending, "handling_fee", 0),
                        discount=pending.discount,
                        coupon_code=pending.coupon_code,
                        total=pending.total,
                        payment_method="COD",
                        status="REQUEST_SUBMITTED"
                    )

                    # Create order items
                    for item_id, item in cart_items["items"].items():

                        if str(item_id).isdigit():
                            try:
                                product = Product.objects.get(id=int(item_id))
                                OrderItem.objects.create(
                                    order=order,
                                    product=product,
                                    price=Decimal(str(item.get("price", 0))),
                                    quantity=int(item.get("quantity", 1))
                                )
                            except:
                                continue

                        elif str(item_id).startswith("bundle_"):
                            OrderItem.objects.create(
                                order=order,
                                product=None,
                                bundle_name=item.get("name", "Combo"),
                                price=Decimal(str(item.get("price", 0))),
                                quantity=int(item.get("quantity", 1))
                            )

                # Safety: no items
                if not order.items.exists():
                    order.delete()
                    messages.error(request, "Items unavailable. Try again.")
                    return redirect("checkout")

                # Clear cart
                request.session["cart"] = {"store_id": None, "items": {}}

                pending.delete()

                return redirect("order_success", order_id=order.id)

            # =========================
            # UPI FLOW
            # =========================
            elif pending.payment_method == "UPI":

                import razorpay
                from django.conf import settings

                client = razorpay.Client(auth=(
                    settings.RAZORPAY_KEY_ID,
                    settings.RAZORPAY_KEY_SECRET
                ))

                razorpay_order = client.order.create({
                    "amount": int(pending.total * 100),
                    "currency": "INR",
                    "payment_capture": 1
                })

                request.session["razorpay_order_id"] = razorpay_order["id"]
                request.session["pending_id"] = pending.id

                return render(request, "upi_payment.html", {
                    "razorpay_key": settings.RAZORPAY_KEY_ID,
                    "amount": int(pending.total * 100),
                    "razorpay_order_id": razorpay_order["id"],
                    "customer_name": pending.customer_name,
                    "phone": pending.phone,
                    "show_floating_cart": False
                })

        # =========================
        # GET REQUEST
        # =========================
        return render(request, "verify_otp.html", {
            "pending_order": pending,
            "expiry_seconds": expiry_seconds,
            "attempts_left": 3 - pending.otp_attempts,
            'simple_navbar': True,
            "show_floating_cart": False
        })

    except Exception as e:
        logger.error(f"VERIFY OTP ERROR: {e}", exc_info=True)
        return render(request, "verify_otp.html", {
            "pending_order": None,
            "error": "Something went wrong. Please try again.",
            "expiry_seconds": 0,
            'simple_navbar': True,
            "show_floating_cart": False
        })'''
  
# =====================================================
# RESEND OTP
# =====================================================
'''def resend_otp(request, pending_id):

    pending = get_object_or_404(PendingOrder, id=pending_id)

    # 🔒 LIMIT 1: Max resend count
    if pending.resend_count >= 3:
        return JsonResponse({
            "error": "Maximum resend limit reached"
        }, status=400)

    # 🔒 LIMIT 2: Cooldown (30 sec)
    if not pending.can_resend():
        return JsonResponse({
            "error": "Please wait 30 seconds before resending OTP"
        }, status=400)

    new_otp = str(random.randint(100000, 999999))

    pending.otp = new_otp
    pending.otp_expiry = timezone.now() + timedelta(minutes=5)
    pending.otp_attempts = 0
    pending.resend_count += 1
    pending.save()

    message = f"Your NEW LOKA OTP is {new_otp}. Valid for 5 minutes."

    try:
        send_sms(pending.phone, message)
    except Exception as e:
        logger.error(f"SMS failed: {e}")

    return JsonResponse({
        "success": True,
        "message": "OTP sent successfully"
    })'''

# =====================================================
# ORDERS
# =====================================================
def order_success(request, order_id):
    order = get_object_or_404(Order, id=order_id)
    return render(request, 'order_success.html', {'order': order, "show_floating_cart": False, 'simple_navbar': True,})


def order_tracking(request, order_id):
    order = get_object_or_404(Order, id=order_id)
    return render(request, 'order_tracking.html', {'order': order,
    "show_floating_cart": False, 'simple_navbar': True,
    })


def my_orders(request):

    phone = request.GET.get('phone', '').strip()

    orders = None

    if phone:
        orders = Order.objects.filter(phone=phone).order_by('-created_at')

    return render(request, 'my_orders.html', {
        'orders': orders,
        'phone': phone,
        'show_navbar': True,
        'simple_navbar': True,
        "show_floating_cart": False
    })


# =====================================================
# SEARCH
# =====================================================
def search_products(request):
    query = request.GET.get('q')
    store_filter = request.GET.get('store')
    sort_option = request.GET.get('sort')
    min_price = request.GET.get('min_price')
    max_price = request.GET.get('max_price')

    cache_key = f"search_{query}_{store_filter}_{sort_option}_{min_price}_{max_price}"

    products = cache.get(cache_key)

    if not products:

        # 🔥 IMPORTANT: optimize query
        products = Product.objects.select_related('store')

        if query:
            products = products.filter(
                Q(name__icontains=query) |
                Q(store__name__icontains=query)
            )

        if store_filter:
            products = products.filter(store_id=store_filter)

        if min_price:
            products = products.filter(price__gte=min_price)

        if max_price:
            products = products.filter(price__lte=max_price)

        # 🔽 DB sorting
        if sort_option == "price_low":
            products = products.order_by('price')
        elif sort_option == "price_high":
            products = products.order_by('-price')
        elif sort_option == "newest":
            products = products.order_by('-id')

        # 🔥 Convert to list for Python sorting
        products = list(products)

        # 🔥 MOST IMPORTANT: open stores first
        products.sort(key=lambda p: not p.store.is_open())

        cache.set(cache_key, products, 120)

    stores = Store.objects.all()

    return render(request, 'search_results.html', {
        'query': query,
        'products': products,
        'stores': stores,
        'selected_store': store_filter,
        'selected_sort': sort_option,
        'min_price': min_price,
        'max_price': max_price,
        "show_floating_cart": True
    })

def search_suggestions(request):
    query = request.GET.get('q', '')

    suggestions = []

    if query:
        products = Product.objects.filter(name__icontains=query)[:5]

        for product in products:
            suggestions.append({
                'id': product.id,
                'name': product.name
            })

    return JsonResponse({'results': suggestions})


# =====================================================
# AJAX DELIVERY CALCULATION
# =====================================================
def calculate_delivery(request):
    latitude = request.GET.get("latitude")
    longitude = request.GET.get("longitude")
    cart = request.session.get('cart', {'items': {}})
    subtotal = Decimal(0)

    for item in cart['items'].values():
        subtotal += Decimal(str(item['price'])) * Decimal(str(item['quantity']))

    if not latitude or not longitude:
        return JsonResponse({"error": "Missing data"}, status=400)

    if subtotal == 0:
        return JsonResponse({
            "delivery_fee": 0,
            "total": 0,
            "distance": 0
        })
    
    latitude = float(latitude)
    longitude = float(longitude)
    subtotal = Decimal(subtotal)

    BUS_STAND_LAT = 16.579644
    BUS_STAND_LON = 74.312721

    distance = calculate_distance(latitude, longitude, BUS_STAND_LAT, BUS_STAND_LON) + 1

    handling_fee = Decimal(12) if subtotal < 149 else Decimal(0)

    delivery_fee = 20

    if subtotal >= 499:
        delivery_fee = Decimal(0)
    else:
        if distance <= 2:
            delivery_fee = Decimal(20)
        else:
            delivery_fee = 20 + max(0, (distance - 2) * 5)
            delivery_fee = math.ceil(delivery_fee)
            delivery_fee = min(delivery_fee, 60)
            delivery_fee = Decimal(delivery_fee)


        if delivery_fee > 60:
            delivery_fee = Decimal(60)

    delivery_fee = Decimal(delivery_fee)

    total = (
        Decimal(subtotal) +
        Decimal(delivery_fee) +
        Decimal(handling_fee)
    )

    # ✅ ROUND PROPERLY
    total = total.quantize(Decimal("1"), rounding=ROUND_HALF_UP)  # integer ₹
    return JsonResponse({
        "delivery_fee": float(delivery_fee),
        "total": float(total),
        "distance": round(distance, 2)
    })
import razorpay
import logging
from django.http import HttpResponse
from django.shortcuts import redirect
from django.conf import settings
from django.db import transaction
from decimal import Decimal

logger = logging.getLogger(__name__)

def payment_success(request):
    import razorpay
    import logging
    from decimal import Decimal
    from django.http import HttpResponse
    from django.shortcuts import redirect
    from django.conf import settings
    from django.db import transaction

    logger = logging.getLogger(__name__)

    try:
        # --------------------------------------------------
        # STEP 1 : GET RAZORPAY RESPONSE PARAMS
        # --------------------------------------------------
        payment_id = request.GET.get("razorpay_payment_id", "").strip()
        razorpay_order_id = request.GET.get("razorpay_order_id", "").strip()
        signature = request.GET.get("razorpay_signature", "").strip()
        pending_id = request.GET.get("pending_id", "").strip()

        logger.info("========== PAYMENT SUCCESS START ==========")
        logger.info(f"PAYMENT_ID: {payment_id}")
        logger.info(f"ORDER_ID: {razorpay_order_id}")
        logger.info(f"PENDING_ID: {pending_id}")

        # --------------------------------------------------
        # STEP 2 : BASIC VALIDATION
        # --------------------------------------------------
        if not payment_id or not razorpay_order_id or not signature:
            logger.error("Missing Razorpay parameters")
            return HttpResponse("Invalid payment response")

        if not pending_id:
            logger.error("Missing pending_id")
            return HttpResponse("Invalid order reference")

        # --------------------------------------------------
        # STEP 3 : DUPLICATE ORDER PROTECTION
        # --------------------------------------------------
        existing_order = Order.objects.filter(payment_id=payment_id).first()

        if existing_order:
            logger.warning("Duplicate callback detected")
            return redirect("order_success", order_id=existing_order.id)

        # --------------------------------------------------
        # STEP 4 : FETCH PENDING ORDER
        # --------------------------------------------------
        try:
            pending = PendingOrder.objects.get(id=int(pending_id))
        except PendingOrder.DoesNotExist:
            logger.error("Pending order not found")
            return HttpResponse("Invalid order reference")

        if pending.payment_method != "UPI":
            logger.error("Pending order not UPI")
            return HttpResponse("Invalid payment flow")

        # Prevent duplicate process
        if pending.is_payment_processed:
            existing_order = Order.objects.filter(
                phone=pending.phone,
                payment_id=payment_id
            ).first()

            if existing_order:
                return redirect("order_success", order_id=existing_order.id)

        # --------------------------------------------------
        # STEP 5 : RAZORPAY CLIENT
        # --------------------------------------------------
        client = razorpay.Client(auth=(
            settings.RAZORPAY_KEY_ID,
            settings.RAZORPAY_KEY_SECRET
        ))

        # --------------------------------------------------
        # STEP 6 : SIGNATURE VERIFY
        # --------------------------------------------------
        try:
            client.utility.verify_payment_signature({
                "razorpay_order_id": razorpay_order_id,
                "razorpay_payment_id": payment_id,
                "razorpay_signature": signature
            })
        except Exception as e:
            logger.error(f"Signature failed: {str(e)}")
            return HttpResponse("Payment verification failed")

        # --------------------------------------------------
        # STEP 7 : FETCH PAYMENT DETAILS
        # --------------------------------------------------
        try:
            payment = client.payment.fetch(payment_id)
        except Exception as e:
            logger.error(f"Payment fetch failed: {str(e)}")
            return HttpResponse("Unable to verify payment")

        payment_status = payment.get("status")
        actual_amount = payment.get("amount")
        expected_amount = to_paise(pending.total)

        logger.info(f"PAYMENT STATUS: {payment_status}")
        logger.info(f"EXPECTED: {expected_amount}")
        logger.info(f"ACTUAL: {actual_amount}")

        # --------------------------------------------------
        # STEP 8 : STRICT CHECKS
        # --------------------------------------------------
        if payment_status != "captured":
            logger.error("Payment not captured")
            return HttpResponse("Payment not completed")

        if actual_amount != expected_amount:
            logger.error("Amount mismatch")
            return HttpResponse("Invalid payment amount")

        # --------------------------------------------------
        # STEP 9 : STORE STATUS CHECK
        # --------------------------------------------------
        try:
            store = Store.objects.get(id=pending.store_id)
        except:
            logger.error("Store missing")
            return HttpResponse("Store unavailable")

        if not store.is_open():
            logger.warning("Store closed after payment")
            return HttpResponse("Store temporarily unavailable. Contact support.")

        # --------------------------------------------------
        # STEP 10 : CREATE ORDER (ATOMIC)
        # --------------------------------------------------
        with transaction.atomic():

            # Lock pending row
            pending = PendingOrder.objects.select_for_update().get(id=pending.id)

            if pending.is_payment_processed:
                existing_order = Order.objects.filter(
                    payment_id=payment_id
                ).first()

                if existing_order:
                    return redirect("order_success", order_id=existing_order.id)

            order = Order.objects.create(
                store_id=pending.store_id,
                customer_name=pending.customer_name,
                phone=pending.phone,
                address=pending.address,
                latitude=pending.latitude,
                longitude=pending.longitude,
                subtotal=pending.subtotal,
                delivery_fee=pending.delivery_fee,
                handling_fee=pending.handling_fee,
                discount=pending.discount,
                coupon_code=pending.coupon_code,
                total=pending.total,
                payment_method="UPI",
                payment_id=payment_id,
                status="REQUEST_SUBMITTED"
            )

            cart_items = pending.items_snapshot or {}

            for item_id, item in cart_items.get("items", {}).items():

                # PRODUCT
                if str(item_id).isdigit():
                    try:
                        product = Product.objects.get(id=int(item_id))

                        OrderItem.objects.create(
                            order=order,
                            product=product,
                            quantity=int(item.get("quantity", 1)),
                            price=Decimal(str(item.get("price", 0)))
                        )
                    except Exception as e:
                        logger.warning(f"Product skipped: {e}")

                # BUNDLE
                elif str(item_id).startswith("bundle_"):
                    OrderItem.objects.create(
                        order=order,
                        product=None,
                        bundle_name=item.get("name", "Combo"),
                        quantity=int(item.get("quantity", 1)),
                        price=Decimal(str(item.get("price", 0)))
                    )

            # Mark processed
            pending.is_payment_processed = True
            pending.save()

        # --------------------------------------------------
        # STEP 11 : CLEANUP
        # --------------------------------------------------
        request.session.pop("pending_id", None)
        request.session.pop("razorpay_order_id", None)
        request.session.pop("razorpay_amount", None)
        request.session["cart"] = {
            "store_id": None,
            "items": {}
        }

        pending.delete()

        logger.info(f"ORDER CREATED: {order.id}")
        logger.info("========== PAYMENT SUCCESS END ==========")

        # --------------------------------------------------
        # STEP 12 : SUCCESS PAGE
        # --------------------------------------------------
        return redirect("order_success", order_id=order.id)

    except Exception as e:
        logger.error(f"CRITICAL PAYMENT ERROR: {str(e)}", exc_info=True)
        return HttpResponse("Something went wrong. Please contact support.")

def mark_out_for_delivery(request, order_id):

    if not request.user.is_staff:
        return JsonResponse({"error": "Unauthorized"}, status=403)

    order = get_object_or_404(Order, id=order_id)

    order.status = "OUT_FOR_DELIVERY"
    order.save()

    try:
        message = f"""Your order #{order.id} is out for delivery 🚴 Delivery Partner Phone: {order.delivery_partner_phone}"""

        send_sms(order.phone, message)

    except Exception as e:
        logger.error(f"Out for delivery SMS failed: {e}")

    return JsonResponse({
        "success": True
    })



import razorpay
from django.conf import settings

def cancel_order(request, order_id):

    order = get_object_or_404(Order, id=order_id)

    # Allow cancellation only before delivery process advances
    if order.status not in ["REQUEST_SUBMITTED", "ACCEPTED"]:
        return redirect("order_tracking", order_id=order.id)

    # -----------------------
    # CASE 1: COD
    # -----------------------
    if order.payment_method == "COD":
        order.status = "CANCELLED"
        order.save()
        return redirect("order_tracking", order_id=order.id)

    # -----------------------
    # CASE 2: UPI → Refund Required
    # -----------------------
    if order.payment_method == "UPI":

        if order.is_refunded:
            return redirect("order_tracking", order_id=order.id)

        client = razorpay.Client(auth=(
            settings.RAZORPAY_KEY_ID,
            settings.RAZORPAY_KEY_SECRET
        ))

        refund_amount = int(order.total * 100)

        refund = client.payment.refund(order.payment_id, {
            "amount": refund_amount
        })

        order.status = "CANCELLED"
        order.refund_id = refund["id"]
        order.refund_amount = order.total
        order.is_refunded = True
        order.save()

        return redirect("order_tracking", order_id=order.id)

from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle
from reportlab.lib import colors
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.lib.units import inch
from django.http import HttpResponse
import io


def generate_invoice(request, order_id):

    order = get_object_or_404(Order, id=order_id)

    buffer = io.BytesIO()
    doc = SimpleDocTemplate(buffer)
    elements = []

    styles = getSampleStyleSheet()

    # 🔹 Title
    elements.append(Paragraph("<b>LOKA - Online Store</b>", styles['Title']))
    elements.append(Spacer(1, 0.3 * inch))

    elements.append(Paragraph(f"Invoice for Order #{order.id}", styles['Heading2']))
    elements.append(Spacer(1, 0.2 * inch))

    # 🔹 Customer Info
    elements.append(Paragraph(f"<b>Customer:</b> {order.customer_name}", styles['Normal']))
    elements.append(Paragraph(f"<b>Phone:</b> {order.phone}", styles['Normal']))
    elements.append(Paragraph(f"<b>Address:</b> {order.address}", styles['Normal']))
    elements.append(Spacer(1, 0.3 * inch))

    # 🔹 Table Data
    data = [["Product", "Qty", "Price", "Subtotal"]]

    for item in order.items.all():

        subtotal = item.price * item.quantity

        if item.product:
            name = item.product.name
        else:
            name = item.bundle_name

        data.append([
            name,
            str(item.quantity),
            f"₹{item.price}",
            f"₹{subtotal}"
        ])

    # Add summary rows
    data.append(["", "", "Subtotal:", f"₹{order.subtotal}"])

    if order.delivery_fee > 0:
        data.append(["", "", "Delivery:", f"₹{order.delivery_fee}"])

    if order.handling_fee > 0:
        data.append(["", "", "handling Fee:", f"₹{order.handling_fee}"])

    if order.discount > 0:
        data.append(["", "", "Coupon Discount:", f"-₹{order.discount}"])

    data.append(["", "", "Total:", f"₹{order.total}"])

    table = Table(data, colWidths=[2.5 * inch, 0.7 * inch, 1 * inch, 1 * inch])

    table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.lightgrey),
        ('GRID', (0, 0), (-1, -1), 0.5, colors.grey),
        ('ALIGN', (1, 1), (-1, -1), 'CENTER')
    ]))

    elements.append(table)
    elements.append(Spacer(1, 0.4 * inch))

    elements.append(Paragraph(f"<b>Payment Method:</b> {order.payment_method}", styles['Normal']))
    elements.append(Paragraph(f"<b>Status:</b> {order.status}", styles['Normal']))

    if order.is_refunded:
        elements.append(Paragraph(f"<b>Refunded:</b> ₹{order.refund_amount}", styles['Normal']))

    doc.build(elements)
    buffer.seek(0)

    response = HttpResponse(buffer.getvalue(), content_type='application/pdf')

    # 🔥 IMPORTANT LINE
    response['Content-Disposition'] = 'inline; filename="invoice.pdf"'

    return response


from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.lib.units import inch
from reportlab.lib import colors
from reportlab.platypus import TableStyle
from django.http import HttpResponse
import io
from .models import Order


def generate_delivery_pdf(request, order_id):

    order = get_object_or_404(Order, id=order_id)

    buffer = io.BytesIO()
    doc = SimpleDocTemplate(buffer)
    elements = []
    styles = getSampleStyleSheet()

    elements.append(Paragraph("<b>Delivery Slip</b>", styles['Title']))
    elements.append(Spacer(1, 0.3 * inch))

    elements.append(Paragraph(f"<b>Order ID:</b> #{order.id}", styles['Normal']))
    elements.append(Spacer(1, 0.2 * inch))

    elements.append(Paragraph(f"<b>Customer:</b> {order.customer_name}", styles['Normal']))

    # Phone with Call link
    call_link = f"tel:{order.phone}"

    elements.append(Paragraph(
        f"<b>Phone:</b> {order.phone}  |  <a href='{call_link}' color='blue'>Call Now</a>",
        styles['Normal']
    ))
    
    elements.append(Paragraph(f"<b>Store:</b> {order.store.name}", styles['Normal']))

    elements.append(Spacer(1, 0.2 * inch))

    # Address
    elements.append(Paragraph(f"<b>Address:</b> {order.address}", styles['Normal']))

    # Google Maps Link (using latitude & longitude)
    if order.latitude and order.longitude:
        map_link = f"https://www.google.com/maps?q={order.latitude},{order.longitude}"
        elements.append(Paragraph(
            f"<b>Google Maps:</b> <a href='{map_link}' color='blue'>Open Location</a>",
            styles['Normal']
        ))

    elements.append(Spacer(1, 0.3 * inch))

    data = [["Product", "Qty", "Price", "Subtotal"]]

    for item in order.items.all():
        subtotal = item.price * item.quantity
        data.append([
            item.product.name if item.product else item.bundle_name,
            str(item.quantity),
            f"₹{item.price}",
            f"₹{subtotal}"
        ])

    # Summary rows

    data.append(["", "", "Subtotal:", f"₹{order.subtotal}"])

    if order.delivery_fee > 0:
        data.append(["", "", "Delivery Fee:", f"₹{order.delivery_fee}"])

    if order.handling_fee > 0:
        data.append(["", "", "handling Fee:", f"₹{order.handling_fee}"])

    if order.discount > 0:
        data.append(["", "", "Discount:", f"-₹{order.discount}"])

    data.append(["", "", "Grand Total:", f"₹{order.total}"])

    table = Table(data, colWidths=[2.5 * inch, 0.7 * inch, 1 * inch, 1 * inch])
    table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.lightgrey),
        ('GRID', (0, 0), (-1, -1), 0.5, colors.grey),
    ]))

    elements.append(table)

    doc.build(elements)
    buffer.seek(0)

    return HttpResponse(buffer, content_type='application/pdf')

def generate_store_pdf(request, order_id):

    order = Order.objects.get(id=order_id)

    buffer = io.BytesIO()
    doc = SimpleDocTemplate(buffer)
    elements = []
    styles = getSampleStyleSheet()

    elements.append(Paragraph("<b>Store Order Slip</b>", styles['Title']))
    elements.append(Spacer(1, 0.3 * inch))

    elements.append(Paragraph(f"<b>Customer:</b> {order.customer_name}", styles['Normal']))
    elements.append(Paragraph(f"<b>Store:</b> {order.store.name}", styles['Normal']))
    elements.append(Spacer(1, 0.3 * inch))

    data = [["Product", "Qty", "Price"]]

    for item in order.items.all():
        data.append([
            item.product.name if item.product else item.bundle_name,
            str(item.quantity),
            f"₹{item.price}"
        ])

    data.append(["", "Total:", f"₹{order.subtotal}"])

    table = Table(data, colWidths=[3 * inch, 1 * inch, 1 * inch])
    table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.lightgrey),
        ('GRID', (0, 0), (-1, -1), 0.5, colors.grey),
    ]))

    elements.append(table)

    doc.build(elements)
    buffer.seek(0)

    return HttpResponse(buffer, content_type='application/pdf')

from django.http import JsonResponse
from .models import Order

def check_free_delivery(request):

    phone = request.GET.get("phone", "").strip()

    if not phone:
        return JsonResponse({"error": "Phone missing"}, status=400)

    order_count = Order.objects.filter(
        phone=phone,
        status="DELIVERED"
    ).count()

    next_is_free = (order_count == 0) or ((order_count + 1) % 5 == 0)
    

    return JsonResponse({
        "order_count": order_count,
        "next_is_free": next_is_free
    })

def combo_detail(request, combo_id):

    combo = Bundle.objects.get(id=combo_id)

    if not combo.store.is_open():
        return JsonResponse({
            "error": "Store is currently closed"
        }, status=400)

    items = []

    for item in combo.items.all():

        items.append({
            "name": item.product.name,
            "price": float(item.product.price),
            "qty": item.quantity
        })

    return JsonResponse({
        "name": combo.name,
        "items": items
    })


import random

'''def send_delivery_otp(request, order_id):

    if not request.user.is_staff:
        return JsonResponse({"error": "Unauthorized"}, status=403)

    order = Order.objects.get(id=order_id)

    otp = str(random.randint(100000,999999))

    order.delivery_otp = otp
    order.delivery_otp_sent_at = timezone.now()
    order.save()

    customer_msg = f"Your delivery OTP is {otp}. Share with delivery partner."
    
    partner_msg = f"Order #{order.id} delivery OTP is {otp}. Collect from customer."

    try:
        # Send to customer
        send_sms(order.phone, customer_msg)

        # Send to delivery partner
        if order.delivery_partner_phone:
            send_sms(order.delivery_partner_phone, partner_msg)

    except Exception as e:
        logger.error(f"Delivery OTP SMS failed: {e}")

    return JsonResponse({
        "success": True,
        "message": "Delivery OTP sent to customer & partner"
    })'''

from django.db.models import Sum, Count
from django.db.models.functions import TruncDate, ExtractHour
import json


def admin_dashboard(request):

    if not request.user.is_staff:
        return redirect("home")

    today = timezone.now().date()

    # Total orders
    total_orders = Order.objects.filter(status="DELIVERED").count()

    # Revenue
    total_revenue = Order.objects.filter(
        status="DELIVERED"
    ).aggregate(Sum("subtotal"))["subtotal__sum"] or 0

    # Today's orders
    todays_orders = Order.objects.filter(
        status="DELIVERED",
        created_at__date=today
    ).count()

    # Average order value
    avg_order_value = total_revenue / total_orders if total_orders else 0

    # Payment split
    cod_orders = Order.objects.filter(
        status="DELIVERED",
        payment_method="COD"
    ).count()

    upi_orders = Order.objects.filter(
        status="DELIVERED",
        payment_method="UPI"
    ).count()

    # Top products
    top_products = OrderItem.objects.filter(
        order__status="DELIVERED",
        product__isnull=False
    ).values(
        "product__name"
    ).annotate(
        total_qty=Sum("quantity")
    ).order_by("-total_qty")[:5]

    # Daily revenue
    daily_sales = Order.objects.filter(
        status="DELIVERED"
    ).annotate(
        day=TruncDate("created_at")
    ).values("day").annotate(
        revenue=Sum("subtotal")
    ).order_by("day")

    # Convert chart data
    labels = [str(d["day"]) for d in daily_sales]
    revenues = [float(d["revenue"]) for d in daily_sales]

    # Repeat customers
    repeat_customers = Order.objects.values("phone").annotate(
        count=Count("id")
    ).filter(count__gt=1).count()

    # Delivery success rate
    delivered = Order.objects.filter(status="DELIVERED").count()
    total = Order.objects.count()

    delivery_success = round((delivered / total) * 100, 2) if total else 0

    # Store leaderboard
    top_stores = Order.objects.filter(
        status="DELIVERED"
    ).values(
        "store__name"
    ).annotate(
        revenue=Sum("subtotal")
    ).order_by("-revenue")[:5]

    # Hourly demand
    hourly_orders = Order.objects.filter(
        status="DELIVERED"
    ).annotate(
        hour=ExtractHour("created_at")
    ).values("hour").annotate(
        count=Count("id")
    ).order_by("hour")

    context = {

        "total_revenue": total_revenue,
        "total_orders": total_orders,
        "todays_orders": todays_orders,
        "avg_order_value": avg_order_value,

        "cod_orders": cod_orders,
        "upi_orders": upi_orders,

        "top_products": top_products,
        "top_stores": top_stores,

        "repeat_customers": repeat_customers,
        "delivery_success": delivery_success,

        "labels": json.dumps(labels),
        "revenues": json.dumps(revenues),
        "show_floating_cart": False,

        "hourly_orders": json.dumps([h["count"] for h in hourly_orders])
    }

    return render(request, "admin_dashboard.html", context)

from .models import Coupon
from .models import CouponUsage

@transaction.atomic
def apply_coupon(request):

    code = request.GET.get("code", "").upper()

    if not code:
        return JsonResponse({
            "success": False,
            "message": "Enter coupon code"
        })
    
    try:
        coupon = Coupon.objects.get(
            code=code,
            is_active=True
        )

    except Coupon.DoesNotExist:
        return JsonResponse({
            "success": False,
            "message": "Invalid coupon"
        })
    
    # 🚨 Prevent reuse per phone
    phone = request.GET.get("phone", "").strip()

    if phone and CouponUsage.objects.filter(coupon=coupon, phone=phone).exists():
        return JsonResponse({
            "success": False,
            "message": "Coupon already used"
        })
    
    try:
        cart = request.session.get('cart') or {'items': {}}
        items = cart.get('items', {})

        subtotal = Decimal(0)

        for item in items.values():
            subtotal += Decimal(item['price']) * item['quantity']
    except:
        subtotal = Decimal(0)

    now = timezone.now()

    if now < coupon.valid_from or now > coupon.valid_to:
        return JsonResponse({
            "success": False,
            "message": "Coupon expired"
        })


    if subtotal < coupon.min_order_value:
        return JsonResponse({
            "success": False,
            "message": f"Minimum order ₹{coupon.min_order_value} required"
        })


    if coupon.used_count >= coupon.usage_limit:
        return JsonResponse({
            "success": False,
            "message": "Coupon usage limit reached"
        })

    

    # Calculate discount

    if coupon.discount_type == "PERCENT":

        discount = subtotal * coupon.discount_value / 100

        if coupon.max_discount:
            discount = min(discount, coupon.max_discount)

    else:

        discount = coupon.discount_value


    return JsonResponse({

        "success": True,
        "discount": float(discount),
        "message": "Coupon applied"

    })

from django.db.models import Sum, Avg
from django.contrib.auth.models import User

def delivery_dashboard(request):

    if not request.user.is_staff:
        return redirect("home")

    partner_id = request.GET.get("partner")

    orders = Order.objects.filter(status="DELIVERED").select_related("assigned_delivery")

    if partner_id:
        orders = orders.filter(assigned_delivery_id=partner_id)

    partners = User.objects.filter(
        delivery_orders__isnull=False
    ).distinct()

    total_orders = orders.count()

    total_distance = orders.aggregate(
        Sum("delivery_distance")
    )["delivery_distance__sum"] or 0

    total_payout = orders.aggregate(
        Sum("delivery_payout")
    )["delivery_payout__sum"] or 0

    avg_time = orders.aggregate(
        Avg("delivery_time_minutes")
    )["delivery_time_minutes__avg"] or 0

    context = {

        "orders": orders,
        "partners": partners,
        "selected_partner": partner_id,

        "total_orders": total_orders,
        "total_distance": round(total_distance,2),
        "total_payout": total_payout,
        "avg_time": round(avg_time,1)

    }

    return render(request,"delivery_dashboard.html",{
        **context,
        "show_navbar": False,
        "show_floating_cart": False
    })

from django.db.models import Sum, Count, F
from .models import Store, Category
from django.db.models import Sum
from datetime import timedelta
from django.db.models import Sum
from datetime import timedelta, datetime
from .models import Store, Category, Order


def store_dashboard(request):

    if not request.user.is_staff:
        return redirect("home")

    category_id = request.GET.get("category")
    store_id = request.GET.get("store")

    start_date = request.GET.get("start_date")
    end_date = request.GET.get("end_date")

    today = timezone.now().date()

    # Default weekly metrics
    if not start_date or not end_date:
        start_date = today - timedelta(days=7)
        end_date = today
    else:
        start_date = datetime.strptime(start_date, "%Y-%m-%d").date()
        end_date = datetime.strptime(end_date, "%Y-%m-%d").date()

    stores = Store.objects.all()

    if category_id:
        stores = stores.filter(category_id=category_id)

    if store_id:
        stores = stores.filter(id=store_id)

    store_data = []

    for store in stores:

        orders = Order.objects.filter(
            store=store,
            status="DELIVERED",
            created_at__date__range=(start_date, end_date)
        )

        sales = orders.aggregate(
            Sum("subtotal")
        )["subtotal__sum"] or 0

        order_count = orders.count()

        commission = sales * store.commission_percent / 100

        payout = sales - commission

        store_data.append({
            "store": store,
            "orders": order_count,
            "sales": round(sales,2),
            "commission": round(commission,2),
            "payout": round(payout,2)
        })

    context = {
        "store_data": store_data,
        "categories": Category.objects.all(),
        "stores": Store.objects.all(),

        "selected_category": category_id,
        "selected_store": store_id,

        "start_date": start_date,
        "end_date": end_date
    }

    return render(request, "store_dashboard.html", {
        **context,
        "show_navbar": False,
        "show_floating_cart": False
    })

def privacy_policy(request):
    return render(request, "privacy_policy.html", {
        "show_floating_cart": False,
        "simple_navbar": True
    })

from django.views.decorators.csrf import csrf_exempt
import json

@csrf_exempt
def razorpay_webhook(request):
    data = json.loads(request.body)

    if data['event'] == 'payment.captured':
        payment = data['payload']['payment']['entity']
        payment_id = payment['id']
        order_id = payment['order_id']

        # mark order as paid safely

    return HttpResponse("OK")

from django.contrib.auth.decorators import login_required
from django.db.models import Sum

import logging
logger = logging.getLogger(__name__)

from django.http import HttpResponse
from django.contrib.auth.decorators import login_required
from django.db.models import Sum

@login_required
def rider_dashboard(request):

    try:
        active_orders = Order.objects.filter(
            assigned_delivery=request.user
        ).exclude(
            status__in=["DELIVERED", "FAILED", "CANCELLED"]
        ).order_by("-created_at")

        completed_orders = Order.objects.filter(
            assigned_delivery=request.user,
            status="DELIVERED"
        ).order_by("-created_at")[:10]

        total_payout = Order.objects.filter(
            assigned_delivery=request.user,
            status="DELIVERED"
        ).aggregate(
            Sum("delivery_payout")
        )["delivery_payout__sum"] or 0

        total_distance = Order.objects.filter(
            assigned_delivery=request.user,
            status="DELIVERED"
        ).aggregate(
            Sum("delivery_distance")
        )["delivery_distance__sum"] or 0

        return render(request, "rider_dashboard.html", {
            "active_orders": active_orders,
            "completed_orders": completed_orders,
            "total_payout": total_payout,
            "total_distance": round(total_distance, 2),
            "show_floating_cart": False,
            "simple_navbar": True
        })

    except Exception as e:
        logger.exception("RIDER DASHBOARD ERROR")
        return HttpResponse("Rider dashboard failed. Check logs.")
    
from django.contrib.auth.decorators import login_required
from django.shortcuts import get_object_or_404, redirect
from django.contrib import messages

@login_required
def rider_update_status(request, order_id, new_status):

    allowed_status = [
        "ACCEPTED",
        "PICKED_UP",
        "OUT_FOR_DELIVERY",
        "DELIVERED",
        "FAILED"
    ]

    if new_status not in allowed_status:
        messages.error(request, "Invalid status")
        return redirect("rider_dashboard")

    order = get_object_or_404(
        Order,
        id=order_id,
        assigned_delivery=request.user
    )

    order.status = new_status
    order.save()

    messages.success(request, f"Order #{order.id} updated to {new_status}")

    return redirect("rider_dashboard")

from django.contrib.auth.decorators import login_required

@login_required
def update_rider_location(request, order_id):

    order = get_object_or_404(
        Order,
        id=order_id,
        assigned_delivery=request.user
    )

    lat = request.GET.get("lat")
    lng = request.GET.get("lng")

    if lat and lng:
        order.rider_latitude = float(lat)
        order.rider_longitude = float(lng)
        order.save(update_fields=["rider_latitude", "rider_longitude"])

    return JsonResponse({"success": True})

def upi_payment(request):

    data = request.session.get("payment_data")

    # ---------------------------------
    # If session missing, rebuild from URL
    # ---------------------------------
    if not data:

        amount = request.GET.get("amount")
        order_id = request.GET.get("order_id")
        display_amount = request.GET.get("display_amount")
        name = request.GET.get("name", "")
        phone = request.GET.get("phone", "")

        if not amount or not order_id:
            return redirect("view_cart")

        data = {
            "razorpay_key": settings.RAZORPAY_KEY_ID,
            "amount": amount,
            "razorpay_order_id": order_id,
            "display_amount": display_amount,
            "customer_name": name,
            "phone": phone,
            "pending_id": request.GET.get("pending_id"),
            "show_floating_cart": False,
            "simple_navbar": True,
        }

    return render(request, "upi_payment.html", data)

