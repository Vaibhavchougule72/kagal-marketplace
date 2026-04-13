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
from .sms_service import send_sms
import logging
logger = logging.getLogger(__name__)


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

    cache_key = f"home_page_{page}"
    data = cache.get(cache_key)

    if not data:

        categories = Category.objects.all()
        stores = Store.objects.all()
        combos = Bundle.objects.filter(is_active=True)\
            .select_related('store')\
            .prefetch_related('items__product')[:6]

        all_products = Product.objects.filter(is_featured=True).select_related('store')

        featured_products_list = [
            p for p in all_products if p.store.is_open()
        ]

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
            "show_floating_cart": False
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
            "price": float(bundle.price),
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
    category = get_object_or_404(Category, id=category_id)
    stores = Store.objects.filter(category=category)
    products = Product.objects.filter(category=category)

    return render(request, 'category_detail.html', {
        'category': category,
        'stores': stores,
        'products': products,
        "show_floating_cart": False
    })


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
    cart = request.session.get('cart')

    if not cart:
        cart = {
            'store_id': product.store.id,
            'items': {}
        }

    # single store rule
    if cart['store_id'] and cart['store_id'] != product.store.id:
        cart = {
            'store_id': product.store.id,
            'items': {}
        }

    product_id = str(product.id)

    # 🔥 GET quantity from request
    qty = int(request.GET.get("qty", 1))

    if product_id in cart['items']:
        cart['items'][product_id]['quantity'] += qty
    else:
        cart['items'][product_id] = {
            'name': product.name,
            'price': float(product.price),
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

    cart = request.session.get('cart')

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
                bundle = Bundle.objects.get(id=bundle_id)

                if not bundle.store.is_open():
                    continue

            except:
                continue

            quantity = Decimal(str(item['quantity']))
            price = Decimal(str(item['price']))

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

            quantity = Decimal(str(item['quantity']))
            price = Decimal(str(item['price']))

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
# =====================================================
def checkout(request):

    cart = request.session.get('cart')

    if not cart or not cart['items']:
        return redirect('home')

    store_id = cart.get('store_id')

    # fallback if missing
    if not store_id:
        first_item = next(iter(cart['items']))

        if str(first_item).startswith("bundle_"):
            bundle_id = int(first_item.split("_")[1])
            bundle = get_object_or_404(Bundle, id=bundle_id, is_active=True)
            store_id = bundle.store.id
        else:
            product = get_object_or_404(Product, id=int(first_item))
            store_id = product.store.id

    store = get_object_or_404(Store, id=store_id)

    context = {
        'cart': cart,
        "show_floating_cart": False
    }

    if not store.is_open():
        context['error'] = f"{store.name} is currently closed."
        return render(request, 'checkout.html', context)

            
    subtotal = Decimal(0)
    upi_only_required = False

    for item_id, item in cart['items'].items():

        price = Decimal(str(item['price']))
        quantity = Decimal(str(item['quantity']))

        subtotal += price * quantity

        # PRODUCT
        if item_id.isdigit():
            try:
                product = Product.objects.get(id=int(item_id))

                # 🔥 CRITICAL FIX: store check
                if not product.store.is_open():
                    context['error'] = f"{product.store.name} is currently closed. Opens at {product.store.next_open_time}"
                    return render(request, 'checkout.html', context)
                   

                if product.upi_only:
                    upi_only_required = True

            except Product.DoesNotExist:
                context['error'] = "Some items are no longer available."
                return render(request, 'checkout.html', context)
             

        # BUNDLE
        elif item_id.startswith("bundle_"):
            try:
                bundle_id = int(item_id.split("_")[1])
                bundle = Bundle.objects.get(id=bundle_id)

                if not bundle.store.is_open():
                    context['error'] = f"{bundle.store.name} is now closed."
                    return render(request, 'checkout.html', context)
                   

            except Bundle.DoesNotExist:
                context['error'] = "Some bundle items are no longer available"
                return render(request, 'checkout.html', context)
    
    

    Handling_fee = Decimal(12) if subtotal < 149 else Decimal(0)
    cod_not_allowed = subtotal < 149

    items = []

    for item_id, item in cart['items'].items():
        items.append({
            "name": item["name"],
            "price": item["price"],
            "quantity": item["quantity"]
        })

    context.update({
        'subtotal': subtotal,
        'Handling_fee': Handling_fee,
        'cod_not_allowed': cod_not_allowed,
        'cart': cart,
        'upi_only_required': upi_only_required,
        "show_floating_cart": False,
        "items": items
    })

    if request.method == "POST":

        name = request.POST.get('name')
        phone = request.POST.get('phone', '').strip()

        if len(phone) < 10:
            context['error'] = "Invalid phone number"
            return render(request, 'checkout.html', context)

        phone = phone[-10:]

        address = request.POST.get('address')
        payment = request.POST.get('payment')
        latitude = request.POST.get('latitude')
        longitude = request.POST.get('longitude')

        if upi_only_required and payment == "COD":
            context['error'] = "Only UPI allowed for selected items"
            return render(request, 'checkout.html', context)


        if not re.match(r'^[6-9]\d{9}$', phone):
            context['error'] = "Invalid phone number"
            return render(request, 'checkout.html', context)
        
        # ---------------------------------
        # Daily order limit protection
        # ---------------------------------
        today = timezone.now().date()

        orders_today = Order.objects.filter(
            phone=phone,
            created_at__date=today
        ).count()

        if orders_today >= 3:
            context['error'] = "Maximum 3 orders allowed per day."
            return render(request, 'checkout.html', context)
        
        # ---------------------------------
        # COD abuse protection
        # ---------------------------------

        cancelled_orders = Order.objects.filter(
            phone=phone,
            status="CANCELLED"
        ).count()

        failed_orders = Order.objects.filter(
            phone=phone,
            status="FAILED"
        ).count()

        bad_orders = cancelled_orders + failed_orders

        if bad_orders >= 3 and payment == "COD":
           context['error'] = "Cash on delivery disabled"
           return render(request, 'checkout.html', context)

        if not latitude or not longitude:
            context['error'] = "Select delivery location"
            return render(request, 'checkout.html', context)

        latitude = float(latitude)
        longitude = float(longitude)

        BUS_STAND_LAT = 16.5775
        BUS_STAND_LON = 74.3169

        distance = calculate_distance(latitude, longitude, BUS_STAND_LAT, BUS_STAND_LON) + 1

        if distance > 7:
            context['error'] = "Delivery not available outside 7 km"
            return render(request, 'checkout.html', context)


        # ------------------------------------------------
        # Check customer order history (5th order free)
        # ----------------------------------------
        order_count = Order.objects.filter(
            phone=phone,
            status="DELIVERED"
        ).count()

        # First order OR every 5th order free
        is_free_delivery_order = (order_count == 0) or ((order_count + 1) % 5 == 0)

        if is_free_delivery_order:
            delivery_fee = Decimal(0)

        elif subtotal >= 499:
            delivery_fee = Decimal(0)

        else:
            if distance <= 2:
                delivery_fee = Decimal(20)
            else:
                delivery_fee = Decimal(20 + ((distance - 2) * 5))

            if delivery_fee > 60:
                delivery_fee = Decimal(60)

        delivery_fee = Decimal(round(delivery_fee, 2))

        coupon_code = request.POST.get("coupon_code")
        discount = Decimal(0)

        if coupon_code:

            try:
                coupon = Coupon.objects.get(code=coupon_code, is_active=True)

                # Prevent reuse
                if CouponUsage.objects.filter(
                    coupon=coupon,
                    phone=phone
                ).exists():

                    context['error'] = "Coupon already used"
                    return render(request, 'checkout.html', context)

                # Calculate discount
                if coupon.discount_type == "PERCENT":
                    discount = subtotal * coupon.discount_value / 100
                else:
                    discount = coupon.discount_value

            except Coupon.DoesNotExist:
                pass
        

        total = subtotal + delivery_fee + Handling_fee - discount
        
        context.update({
            'delivery_fee': delivery_fee,
            'handling_fee': Handling_fee,
            'discount': discount,
            'total': total
        })

        # -----------------------------
        # COD RULE
        # -----------------------------
        if subtotal < 149 and payment == "COD":
            context['error'] = "COD not allowed below ₹149"
            return render(request, 'checkout.html', context)

        otp = str(random.randint(100000, 999999))

        pending = PendingOrder.objects.create(
            store_id=store_id,
            customer_name=name,
            phone=phone,
            address=address,
            latitude=latitude,
            longitude=longitude,

            subtotal=subtotal,
            delivery_fee=delivery_fee,
            Handling_fee=Handling_fee,

            discount=discount,
            coupon_code=coupon_code,

            total=total,

            payment_method=payment,
            items_snapshot=cart,
            otp=otp,
            otp_expiry=timezone.now() + timedelta(minutes=5),
            otp_attempts=0
        )

       

        message = f"LOKA verification code {otp}"

        try:
            sms_response = send_sms(phone, message)

            if not sms_response or not sms_response.get("return"):
                pending.delete()

                context['error'] = "OTP service failed. Please try again."
                return render(request, 'checkout.html', context)
        
        except Exception as e:
            logger.error(f"SMS failed: {e}")

            pending.delete()

            context['error'] = "OTP service failed. Please try again."
            return render(request, 'checkout.html', context)

        return redirect('verify_otp', pending_id=pending.id)

    return render(request, 'checkout.html', context)


# =====================================================
# VERIFY OTP
def verify_otp(request, pending_id):

    pending = get_object_or_404(PendingOrder, id=pending_id)
    # ✅ NEW STEP: Check store status
    store = get_object_or_404(Store, id=pending.store_id)

    if not store.is_open():
        pending.delete()

        from django.contrib import messages
        messages.error(request, f"{store.name} is now closed.")

        return redirect("checkout")

    # 🔒 If already expired (GET request)
    if pending.is_expired():
        return render(request, "verify_otp.html", {
            "pending_order": pending,
            "error": "OTP expired. Please resend OTP.",
            "show_floating_cart": False
        })

    if request.method == "POST":

        entered = request.POST.get("otp", "").strip()

        # 1️⃣ Expiry check again (safety)
        if pending.is_expired():
            return render(request, "verify_otp.html", {
                "pending_order": pending,
                "error": "OTP expired. Please resend OTP.",
                "show_floating_cart": False
            })

        # 2️⃣ Max attempts check
        if pending.otp_attempts >= 3:
            pending.delete()
            return render(request, "verify_otp.html", {
                "error": "Too many wrong attempts. Order cancelled.",
                "show_floating_cart": False
            })

        # 3️⃣ Validate OTP format (must be 6 digits)
        if not entered.isdigit() or len(entered) != 6:
            return render(request, "verify_otp.html", {
                "pending_order": pending,
                "error": "Please enter a valid 6-digit OTP.",
                "show_floating_cart": False
            })

        # 4️⃣ Validate OTP match
        if entered != pending.otp:
            pending.otp_attempts += 1
            pending.save()

            attempts_left = 3 - pending.otp_attempts

            return render(request, "verify_otp.html", {
                "pending_order": pending,
                "error": f"Invalid OTP. {attempts_left} attempt(s) remaining.",
                "show_floating_cart": False
            })

        # ✅ OTP CORRECT

        # -----------------------
        # CASE 1: COD
        # -----------------------
        if pending.payment_method == "COD":

            cart_items = pending.items_snapshot

            for item_id, item in cart_items['items'].items():

                # PRODUCT
                if item_id.isdigit():
                    try:
                        product = Product.objects.get(id=int(item_id))

                        # 🔥 CHECK STORE AGAIN (CRITICAL)
                        if not product.store.is_open():
                            from django.contrib import messages

                            messages.error(request, f"{product.store.name} is now closed.")
                            return redirect("checkout")
                            


                    except Product.DoesNotExist:
                        from django.contrib import messages

                        messages.error(request, "Some items are no longer available")
                        return redirect("checkout")
                    

                # BUNDLE
                elif item_id.startswith("bundle_"):
                    try:
                        bundle_id = int(item_id.split("_")[1])
                        bundle = Bundle.objects.get(id=bundle_id)

                        if not bundle.store.is_open():
                            
                            from django.contrib import messages

                            messages.error(request, f"{bundle.store.name} is now closed.")
                            return redirect("checkout")

                    except Bundle.DoesNotExist:
                        from django.contrib import messages

                        messages.error(request, "Some bundle items are no longer available.")
                        return redirect("checkout")
                       

            order = Order.objects.create(
                store_id=pending.store_id,
                customer_name=pending.customer_name,
                phone=pending.phone,
                address=pending.address,
                latitude=pending.latitude,
                longitude=pending.longitude,
                subtotal=pending.subtotal,
                delivery_fee=pending.delivery_fee,
                Handling_fee=pending.Handling_fee,
                discount=pending.discount,
                coupon_code=pending.coupon_code,
                
                total=pending.total,
                payment_method="COD",
                status="REQUEST_SUBMITTED"
            )

            if pending.coupon_code:
                try:
                    coupon = Coupon.objects.get(code=pending.coupon_code)

                    CouponUsage.objects.create(
                        coupon=coupon,
                        phone=pending.phone
                    )

                    Coupon.objects.filter(code=pending.coupon_code).update(
                        used_count=F("used_count") + 1
                    )

                except Coupon.DoesNotExist:
                    logger.warning("Coupon not found during order creation")

           

            if not cart_items or not cart_items['items']:
                return redirect('home')

            store_id = cart_items.get('store_id')
            

            # fallback if store_id missing
            if not store_id:
                first_item = next(iter(cart_items['items']))
                
                if str(first_item).startswith("bundle_"):
                    bundle_id = int(first_item.split("_")[1])
                    bundle = get_object_or_404(Bundle, id=bundle_id, is_active=True)
                    store_id = bundle.store.id
                else:
                    product = get_object_or_404(Product, id=int(first_item))
                    store_id = product.store.id

            
            request.session['cart'] = {'store_id': None, 'items': {}}
            pending.delete()
            try:
                send_sms(order.phone, f"Order #{order.id} confirmed! Total ₹{order.total}.")
            except Exception as e:
                logger.error(f"Order SMS failed: {e}")

            try:
                send_sms("7038984687", f"New order #{order.id} received")
            except Exception as e:
                logger.error(f"Admin SMS failed: {e}")
            

            return redirect("order_success", order_id=order.id)


        # -----------------------
        # CASE 2: UPI (Razorpay)
        # -----------------------
        elif pending.payment_method == "UPI":

            import razorpay
            from django.conf import settings

            client = razorpay.Client(auth=(
                settings.RAZORPAY_KEY_ID,
                settings.RAZORPAY_KEY_SECRET
            ))

            razorpay_order = client.order.create({
                "amount": int(pending.total * 100),  # ₹ to paise
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

        

    expiry_seconds = int((pending.otp_expiry - timezone.now()).total_seconds())

    if expiry_seconds < 0:
        expiry_seconds = 0

    attempts_left = 3 - pending.otp_attempts

    return render(request, "verify_otp.html", {
        "pending_order": pending,
        "expiry_seconds": expiry_seconds,
        "attempts_left": attempts_left,
        'show_navbar': False,
        "show_floating_cart": False
    })

# =====================================================
# RESEND OTP
# =====================================================
def resend_otp(request, pending_id):

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
    })

# =====================================================
# ORDERS
# =====================================================
def order_success(request, order_id):
    order = get_object_or_404(Order, id=order_id)
    return render(request, 'order_success.html', {'order': order})


def order_tracking(request, order_id):
    order = get_object_or_404(Order, id=order_id)
    return render(request, 'order_tracking.html', {'order': order,
    "show_floating_cart": False
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
    subtotal = request.GET.get("subtotal")

    if not latitude or not longitude or not subtotal:
        return JsonResponse({"error": "Missing data"}, status=400)

    latitude = float(latitude)
    longitude = float(longitude)
    subtotal = Decimal(subtotal)

    BUS_STAND_LAT = 16.5775
    BUS_STAND_LON = 74.3169

    distance = calculate_distance(latitude, longitude, BUS_STAND_LAT, BUS_STAND_LON) + 1

    Handling_fee = Decimal(20) if subtotal < 149 else Decimal(0)

    delivery_fee = 20

    if subtotal >= 499:
        delivery_fee = Decimal(0)
    else:
        if distance <= 2:
            delivery_fee = Decimal(20)
        else:
            delivery_fee = Decimal(20 + ((distance - 2) * 5))

        if delivery_fee > 60:
            delivery_fee = Decimal(60)

    delivery_fee = Decimal(round(delivery_fee, 2))
    total = subtotal + delivery_fee + Handling_fee

    return JsonResponse({
        "delivery_fee": float(delivery_fee),
        "total": float(total),
        "distance": round(distance, 2)
    })


import hmac
import hashlib
from django.http import HttpResponse

def payment_success(request):

    payment_id = request.GET.get("payment_id")
    razorpay_order_id = request.GET.get("order_id")
    signature = request.GET.get("signature")

    if Order.objects.filter(payment_id=payment_id).exists():
        return HttpResponse("Order already created")

    pending_id = request.session.get("pending_id")

    if razorpay_order_id != request.session.get("razorpay_order_id"):
        return HttpResponse("Order ID mismatch")

    if not pending_id:
        return HttpResponse("Invalid session")

    pending = get_object_or_404(PendingOrder, id=pending_id)

    generated_signature = hmac.new(
        bytes(settings.RAZORPAY_KEY_SECRET, 'utf-8'),
        bytes(razorpay_order_id + "|" + payment_id, 'utf-8'),
        hashlib.sha256
    ).hexdigest()

    if generated_signature != signature:
        return HttpResponse("Payment verification failed")
    
    amount = int(request.GET.get("amount", pending.total * 100))

    if int(pending.total * 100) != amount:
        return HttpResponse("Amount mismatch")
    
    # Payment verified → Create order
    order = Order.objects.create(
        store_id=pending.store_id,
        customer_name=pending.customer_name,
        phone=pending.phone,
        address=pending.address,

        latitude=pending.latitude,
        longitude=pending.longitude,

        subtotal=pending.subtotal,
        delivery_fee=pending.delivery_fee,
        Handling_fee=pending.Handling_fee,

        discount=pending.discount,
        coupon_code=pending.coupon_code,

        total=pending.total,

        payment_method="UPI",
        status="REQUEST_SUBMITTED",
        payment_id=payment_id
    )

    if pending.coupon_code:
        try:
            coupon = Coupon.objects.get(code=pending.coupon_code)

            CouponUsage.objects.create(
                coupon=coupon,
                phone=pending.phone
            )

            Coupon.objects.filter(code=pending.coupon_code).update(
                used_count=F("used_count") + 1
            )

        except Coupon.DoesNotExist:
            logger.warning("Coupon not found in payment_success")
    

    cart_items = pending.items_snapshot

    for item_id, item in cart_items['items'].items():

        # PRODUCT
        if item_id.isdigit():

            product = get_object_or_404(Product, id=int(item_id))

            OrderItem.objects.create(
                order=order,
                product=product,
                quantity=int(item['quantity']),
                price=Decimal(str(item['price']))
            )

        # BUNDLE
        elif str(item_id).startswith("bundle_"):

            OrderItem.objects.create(
                order=order,
                product=None,
                bundle_name=item["name"],
                quantity=int(item['quantity']),
                price=Decimal(str(item['price']))
            )
            
    

    request.session.pop("pending_id", None)
    request.session.pop("razorpay_order_id", None)

    request.session['cart'] = {'store_id': None, 'items': {}}
    pending.delete()

    return redirect("order_success", order_id=order.id)


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

from django.contrib import messages

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

    if order.Handling_fee > 0:
        data.append(["", "", "Handling Fee:", f"₹{order.Handling_fee}"])

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
    return HttpResponse(buffer, content_type='application/pdf')


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

    if order.Handling_fee > 0:
        data.append(["", "", "Handling Fee:", f"₹{order.Handling_fee}"])

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

    phone = request.GET.get("phone")

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

def send_delivery_otp(request, order_id):

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
    })

from django.db.models import Sum, Count
from django.db.models.functions import TruncDate, ExtractHour
from django.utils import timezone
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
    ).aggregate(Sum("total"))["total__sum"] or 0

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
        revenue=Sum("total")
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
        revenue=Sum("total")
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

def apply_coupon(request):

    code = request.GET.get("code", "").upper()
    subtotal = Decimal(request.GET.get("subtotal", 0))

    try:
        coupon = Coupon.objects.select_for_update().get(
            code=code,
            is_active=True
        )

    except Coupon.DoesNotExist:
        return JsonResponse({
            "success": False,
            "message": "Invalid coupon"
        })


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
from django.utils import timezone
from datetime import timedelta
from django.db.models import Sum
from django.utils import timezone
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
            Sum("total")
        )["total__sum"] or 0

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

def splash(request):
    return render(request, "splash.html")