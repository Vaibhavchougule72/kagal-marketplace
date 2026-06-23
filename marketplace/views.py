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
from .models import Category, Store, Product, Order, OrderItem, PendingOrder, CheckoutLead, Expense
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
from .models import Banner
from .models import Store
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from django.conf import settings
import os

from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from django.views.decorators.csrf import csrf_exempt
import json
import razorpay
from django.db.models import Avg
from django.views.decorators.http import require_POST
from .models import StoreRating
from .firebase import send_push_notification
from .models import DeviceToken
from django.db.models import Sum
from datetime import datetime
import traceback
from .models import OfferSlider

MAX_CART_QTY = 50

def safe_qty(value):

    try:

        qty = int(value)

    except:

        return 1

    if qty < 1:
        return 1

    if qty > MAX_CART_QTY:
        return MAX_CART_QTY

    return qty

font_path = os.path.join(
    settings.BASE_DIR,
    "static/fonts/NotoSans-Regular.ttf"
)

pdfmetrics.registerFont(
    TTFont("Noto", font_path)
)

def is_store_open_cached(store: Store):
    key = f"store_open_{store.id}"
    status = cache.get(key)

    if status is None:
        try:
            status = store.is_open()
        except:
            status = False
        cache.set(key, status, 60)

    return status

def get_cart_details(cart):
    items = []
    subtotal = Decimal(0)

    product_ids = []
    bundle_ids = []

    for item_id in cart.get("items", {}):
        if item_id.isdigit():
            product_ids.append(int(item_id))
        elif item_id.startswith("bundle_"):
            bundle_ids.append(int(item_id.split("_")[1]))

    products = {
        p.id: p for p in Product.objects.filter(id__in=product_ids)
    }

    bundles = {
        b.id: b for b in Bundle.objects.filter(id__in=bundle_ids, is_active=True)
    }

    for item_id, item in cart.get("items", {}).items():

        qty = safe_qty(item.get("quantity", 1))

        if item_id.isdigit():
            product = products.get(int(item_id))
            if not product:
                continue
            price = product.discount_price or product.price

        else:
            bundle_id = int(item_id.split("_")[1])
            bundle = bundles.get(bundle_id)
            if not bundle:
                continue
            price = bundle.price

        subtotal += price * qty

    return subtotal

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

    # -------------------------
    # BASIC DATA (NO CACHE)
    # -------------------------
    categories = Category.objects.all()
    stores = Store.objects.prefetch_related('timings')
    banners = Banner.objects.filter(is_active=True).order_by('priority')

    popup_banner = banners.filter(is_popup=True).first()
    main_banner = banners.filter(is_popup=False).first()
    featured_stores = [
        s for s in Store.objects.filter(
            is_featured=True
        ).prefetch_related(
            "product_set",
            "timings"
        ).order_by(
            "featured_priority"
        )
        if is_store_open_cached(s)
    ]

    for store in featured_stores:

        store.featured_products = Product.objects.filter(
            store=store,
            is_featured=True
        )[:4]

    # =====================================================
    # 🔥 COMBOS (CACHE)
    # =====================================================
    combo_cache_key = "home_combos"

    combo_ids = cache.get(combo_cache_key)

    if not combo_ids:

        all_combos = Bundle.objects.filter(is_active=True)\
            .select_related('store')\
            .prefetch_related('items__product')

        store_status_map = {}

        for c in all_combos:
            sid = c.store.id

            if sid not in store_status_map:
                try:
                    # ✅ optional cache for store open
                    status = is_store_open_cached(c.store)
                except:
                    status = False

                store_status_map[sid] = status

        open_combos = [c for c in all_combos if store_status_map.get(c.store.id)]

        combo_ids = [c.id for c in open_combos[:6]]

        cache.set(combo_cache_key, combo_ids, 60)

    combos = Bundle.objects.filter(id__in=combo_ids)\
        .select_related('store')\
        .prefetch_related('items__product')

    # =====================================================
    # 🔥 FEATURED PRODUCTS (CACHE + PAGINATION SAFE)
    # =====================================================
    product_cache_key = "home_featured_ids"

    product_ids = cache.get(product_cache_key)

    if product_ids is None:

        all_products = Product.objects.filter(is_featured=True)\
            .select_related('store')\
            .prefetch_related('store__timings')

        store_status_map = {}

        for p in all_products:
            sid = p.store.id

            if sid not in store_status_map:
                try:
                    status = is_store_open_cached(p.store)
                except:
                    status = False

                store_status_map[sid] = status

        open_products = [
            p for p in all_products
            if store_status_map.get(p.store.id)
            and p.is_available_now()
        ]

        # 🔥 HERO PRIORITY SORT
        hero_products = sorted(
            [p for p in open_products if p.is_hero],
            key=lambda x: x.hero_priority
        )

        normal_products = [p for p in open_products if not p.is_hero]

        final_products = hero_products + normal_products

        product_ids = [p.id for p in final_products]

        cache.set(product_cache_key, product_ids, 30)
    # remove deleted product ids from cache
    valid_ids = list(
        Product.objects.filter(id__in=product_ids)
        .values_list("id", flat=True)
    )

    product_ids = [pid for pid in product_ids if pid in valid_ids]
    # 🔥 FETCH PRODUCTS FROM IDS (ORDER SAFE)
    products_qs = Product.objects.filter(id__in=product_ids)\
        .select_related('store')

    products_ordered = sorted(
        products_qs,
        key=lambda x: product_ids.index(x.id)
    )

    paginator = Paginator(products_ordered, 12)
    featured_products = paginator.get_page(page)

    offer_sliders = OfferSlider.objects.filter(
        is_active=True
    ).order_by("priority")
    # =====================================================
    # FINAL RESPONSE
    # =====================================================
    return render(request, "home.html", {
        "categories": categories,
        "stores": stores,
        "combos": combos,
        "featured_products": products_ordered[:10],
        "main_banner": main_banner,
        "popup_banner": popup_banner,
        "offer_sliders": offer_sliders,
        "featured_stores": featured_stores,
        "show_floating_cart": True,
    })
# =====================================================
# STORES
# =====================================================
def all_stores(request):
    stores = Store.objects.select_related('category').all()
    return render(request, 'all_stores.html', {'stores': stores})



def store_detail(request, store_id):

    cache_key = f"store_{store_id}"

    data = cache.get(cache_key)

    # =========================
    # CACHE MISS
    # =========================
    if not data:

        store = get_object_or_404(Store, id=store_id)

        products = Product.objects.filter(store=store)\
            .select_related("category", "store")\
            .order_by('-id')

        bundles = Bundle.objects.filter(
            store=store,
            is_active=True
        )

        # ✅ STORE ONLY IDS
        cache_data = {
            "store_id": store.id,
            "product_ids": list(products.values_list("id", flat=True)),
            "bundle_ids": list(bundles.values_list("id", flat=True))
        }

        cache.set(cache_key, cache_data, 30)

        data = cache_data

    # =========================
    # REBUILD FROM CACHE
    # =========================
    store = get_object_or_404(Store, id=data["store_id"])
    # =========================
    # FILTER VALUES
    # =========================
    query = request.GET.get("q", "")
    min_price = request.GET.get("min_price")
    max_price = request.GET.get("max_price")
    sort = request.GET.get("sort")

    products = Product.objects.filter(
        id__in=data["product_ids"]
    ).select_related(
        "category",
        "store"
    )
    for product in products:

        product.available_now = product.is_available_now()
    
    # =========================
    # SEARCH
    # =========================
    if query:
        products = products.filter(
            name__icontains=query
        )

    # =========================
    # PRICE FILTER
    # =========================
    if min_price:
        products = products.filter(
            price__gte=min_price
        )

    if max_price:
        products = products.filter(
            price__lte=max_price
        )

    # =========================
    # SORTING
    # =========================
    if sort == "price_low":
        products = products.order_by("price")

    elif sort == "price_high":
        products = products.order_by("-price")

    elif sort == "newest":
        products = products.order_by("-id")

    else:
        products = products.order_by("-id")

    bundles = Bundle.objects.filter(
        id__in=data["bundle_ids"],
        is_active=True
    )

    featured_products = Product.objects.filter(
        store=store,
        is_featured=True
    ).order_by("-id")[:10]
    if request.headers.get("X-Requested-With") == "XMLHttpRequest":

        return render(
            request,
            "partials/store_products.html",
            {
                "products": products
            }
        )

    return render(request, "store_detail.html", {
        "store": store,
        "featured_products": featured_products,
        "products": products,
        "bundles": bundles,
        "show_floating_cart": True,
        # FILTER VALUES
        "query": query,
        "selected_sort": sort,
        "min_price": min_price,
        "max_price": max_price,
        "show_navbar": False,
        "simple_navbar": False,
        "show_floating_cart": True
    })

def add_bundle_to_cart(request, bundle_id):

    bundle = get_object_or_404(Bundle, id=bundle_id, is_active=True)

    # ✅ ADD THIS
    if not is_store_open_cached(bundle.store):
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


from django.db.models import Min, Count

def category_stores(request, category_id):

    category = get_object_or_404(
        Category,
        id=category_id
    )

    stores = (
        Store.objects
        .filter(category=category)
        .annotate(
            min_price=Min("product__price"),
            total_products=Count("product")
        )
    )

    return render(
        request,
        "category_stores.html",
        {
            "category": category,
            "stores": stores,
            "show_navbar": False,
            "show_floating_cart": False,
        }
    )


def category_products(request, category_id):

    category = get_object_or_404(Category, id=category_id)

    query = request.GET.get("q", "")
    store_filter = request.GET.get("store")
    min_price = request.GET.get("min_price")
    max_price = request.GET.get("max_price")
    sort = request.GET.get("sort")

    products = Product.objects.filter(category=category)\
        .select_related('store')\
        .prefetch_related('store__timings')

    # 🔍 SEARCH
    if query:
        products = products.filter(name__icontains=query)

    # 🏪 STORE FILTER
    if store_filter:
        products = products.filter(store_id=store_filter)

    # 💰 PRICE FILTER
    if min_price:
        products = products.filter(price__gte=min_price)

    if max_price:
        products = products.filter(price__lte=max_price)

    # ↕ SORTING
    if sort == "price_low":
        products = products.order_by("price")
    elif sort == "price_high":
        products = products.order_by("-price")
    elif sort == "newest":
        products = products.order_by("-id")
    else:
        products = products.order_by("-id")

    # 🔥 STORE LIST FOR FILTER
    stores = Store.objects.filter(category=category)

    return render(request, 'category_products.html', {
        'category': category,
        'products': products,
        'stores': stores,
        'query': query,
        'selected_store': store_filter,
        'selected_sort': sort,
        'min_price': min_price,
        'max_price': max_price,
        "show_floating_cart": True
    })


# =====================================================
# CART
# =====================================================
def add_to_cart(request, product_id):

    product = get_object_or_404(Product, id=product_id, is_active=True)

    if not product.is_available_now():

        return JsonResponse({
            "success": False,
            "error": "Product unavailable at this time"
        })

    if not is_store_open_cached(product.store):
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
        qty = safe_qty(
            request.GET.get("qty", 1)
        )
    except:
        qty = 1

    if product_id in cart['items']:
        cart['items'][product_id]['quantity'] += qty
    else:
        # ✅ Use discount if available
        source = request.GET.get("source", "normal")

        # ✅ Apply discount ONLY for homepage
        if source == "home" and product.discount_price:
            final_price = product.discount_price
        else:
            final_price = product.price

        cart['items'][product_id] = {
            'name': product.name,
            'quantity': qty,
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

def cross_sell_status(request):

    cart = request.session.get(
        "cart",
        {
            "store_id": None,
            "items": {}
        }
    )

    subtotal = get_cart_details(cart)

    threshold = Decimal("249")

    progress = 0

    if subtotal > 0:
        progress = min(
            100,
            (subtotal / threshold) * 100
        )

    return JsonResponse({
        "subtotal": float(subtotal),
        "remaining": float(
            max(Decimal("0"), threshold - subtotal)
        ),
        "progress": float(progress),
        "qualified": subtotal >= threshold
    })

def view_cart(request):

    cart = request.session.get('cart', {
        'store_id': None,
        'items': {}
    })

    items = []
    total_savings = Decimal(0)
    subtotal = Decimal(0)

    # =========================
    # PRELOAD DATA (OPTIMIZED)
    # =========================
    product_ids = [int(i) for i in cart['items'] if i.isdigit()]
    bundle_ids = [int(i.split("_")[1]) for i in cart['items'] if i.startswith("bundle_")]

    products_map = {
        p.id: p for p in Product.objects.filter(id__in=product_ids).select_related("store")
    }

    bundles_map = {
        b.id: b for b in Bundle.objects.filter(id__in=bundle_ids, is_active=True).select_related("store")
    }

    # =========================
    # STORE OPEN CACHE (🔥 FIX)
    # =========================
    store_status_map = {}

    cleaned_items = {}

    for item_id, item in cart["items"].items():

        # PRODUCT
        if item_id.isdigit():

            if int(item_id) not in products_map:
                continue

        # BUNDLE
        elif item_id.startswith("bundle_"):

            try:

                bundle_id = int(item_id.split("_")[1])

            except:
                continue

            if bundle_id not in bundles_map:
                continue

        else:
            continue

        cleaned_items[item_id] = {
            "quantity": safe_qty(
                item.get("quantity", 1)
            )
        }

    cart["items"] = cleaned_items
    request.session["cart"] = cart
    request.session.modified = True
    

    # =========================
    # BUILD CART ITEMS
    # =========================
    for item_id, item in cart['items'].items():

        qty = safe_qty(item.get('quantity', 1))

        # ----------------------
        # PRODUCT
        # ----------------------
        if item_id.isdigit():

            product = products_map.get(int(item_id))
            if not product:
                continue

            if product.store.id not in store_status_map:
                store_status_map[product.store.id] = is_store_open_cached(product.store)

            if not store_status_map[product.store.id]:
                continue

            original_price = product.price
            final_price = product.discount_price or product.price

            line_total = final_price * qty
            subtotal += line_total

            # 🔥 SAVINGS CALCULATION
            if product.discount_price:
                total_savings += (original_price - final_price) * qty

            

            items.append({
                "key": item_id,
                "product": product,
                "name": product.name,
                "quantity": qty,
                "price": final_price,
                "subtotal": line_total
            })

        # ----------------------
        # BUNDLE
        # ----------------------
        elif item_id.startswith("bundle_"):

            bundle_id = int(item_id.split("_")[1])
            bundle = bundles_map.get(bundle_id)

            if not bundle:
                continue

            if bundle.store.id not in store_status_map:
                store_status_map[bundle.store.id] = is_store_open_cached(bundle.store)

            if not store_status_map[bundle.store.id]:
                continue

            price = bundle.price
            line_total = price * qty
            # bundles no savings (optional future)

            subtotal += line_total

            items.append({
                "key": item_id,
                "product": None,
                "name": bundle.name,
                "quantity": qty,
                "price": price,
                "subtotal": line_total
            })

    # =========================
    # BUSINESS RULES
    # =========================
    remaining_to_149 = Decimal(149) - subtotal if subtotal < 149 else Decimal(0)
    cod_not_allowed = subtotal < 149
    remaining_to_free_delivery = Decimal(999) - subtotal if subtotal < 999 else Decimal(0)

    # =========================
    # CLEAN EMPTY CART
    # =========================
    if not items:
        request.session['cart'] = {
            'store_id': None,
            'items': {}
        }
        request.session.modified = True

    # 🔥 FREE DELIVERY PROGRESS
    FREE_DELIVERY_THRESHOLD = Decimal(999)

    if subtotal < FREE_DELIVERY_THRESHOLD:
        remaining_amount = FREE_DELIVERY_THRESHOLD - subtotal
        progress_percent = (subtotal / FREE_DELIVERY_THRESHOLD) * 100
    else:
        remaining_amount = Decimal(0)
        progress_percent = 100

    
    cross_sell_threshold = Decimal("249")

    show_cross_sell = (
        subtotal >= Decimal("150")
        and subtotal < cross_sell_threshold
    )

    remaining_cross_sell = max(
        Decimal("0"),
        cross_sell_threshold - subtotal
    )

    cross_sell_progress = min(
        100,
        (subtotal / cross_sell_threshold) * 100
    )

    recommended_products = []

    if cart.get("store_id"):

        store = Store.objects.filter(
            id=cart["store_id"]
        ).first()

        if store:

            cart_product_ids = [
                int(i)
                for i in cart["items"]
                if i.isdigit()
            ]

            recommended_products = (
                Product.objects
                .filter(
                    store=store,
                    is_active=True
                )
                .exclude(
                    id__in=cart_product_ids
                )
                .order_by("price")[:6]
            )

    # =========================
    # RESPONSE
    # =========================
    return render(request, 'cart_partial.html', {
        'items': items,
        'subtotal': subtotal,
        'remaining_to_149': remaining_to_149,
        'cod_not_allowed': cod_not_allowed,
        'remaining_to_free_delivery': remaining_to_free_delivery,
        "show_floating_cart": False,
        'total_savings': total_savings,
        'remaining_amount': remaining_amount,
        'progress_percent': progress_percent,
        "show_cross_sell": show_cross_sell,
        "remaining_cross_sell": remaining_cross_sell,
        "cross_sell_progress": cross_sell_progress,
        "recommended_products": recommended_products,
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

    # -------------------------
    # CLEAN OLD PENDING ORDERS
    # -------------------------
    PendingOrder.objects.filter(
        created_at__lt=timezone.now() - timedelta(days=7)
    ).delete()

    cart = request.session.get('cart', {'store_id': None, 'items': {}})

    if not cart.get('items'):
        return redirect('home')

    # -------------------------
    # PRELOAD PRODUCTS & BUNDLES (ONE QUERY)
    # -------------------------
    product_ids = [int(i) for i in cart['items'] if i.isdigit()]
    bundle_ids = [int(i.split("_")[1]) for i in cart['items'] if i.startswith("bundle_")]

    products_map = {
        p.id: p for p in Product.objects.filter(id__in=product_ids)
    }

    bundles_map = {
        b.id: b for b in Bundle.objects.filter(id__in=bundle_ids, is_active=True)
    }

    # -------------------------
    # STORE VALIDATION
    # -------------------------
    store_ids = set()

    for item_id in cart['items']:

        if item_id.isdigit():
            product = products_map.get(int(item_id))
            if product:
                store_ids.add(product.store.id)

        elif item_id.startswith("bundle_"):
            bundle = bundles_map.get(int(item_id.split("_")[1]))
            if bundle:
                store_ids.add(bundle.store.id)

    if len(store_ids) != 1:
        return render(request, 'checkout.html', {
            "error": "Cart contains items from multiple stores",
            "show_floating_cart": False
        })
    
    if not store_ids:

        context["error"] = "Cart is empty"

        return render(request, "checkout.html", context)

    store_id = list(store_ids)[0]
    store = get_object_or_404(Store, id=store_id)

    # -------------------------
    # BUILD CART ITEMS
    # -------------------------
    items = []

    for item_id, item in cart['items'].items():

        qty = safe_qty(item.get("quantity", 1))

        # PRODUCT
        if item_id.isdigit():

            product = products_map.get(int(item_id))

            if not product:
                continue

            final_price = product.discount_price or product.price

            items.append({
                "name": product.name,
                "price": final_price,
                "quantity": qty,
                "subtotal": final_price * qty
            })

        # BUNDLE
        elif item_id.startswith("bundle_"):

            bundle = bundles_map.get(int(item_id.split("_")[1]))

            if not bundle:
                continue

            items.append({
                "name": bundle.name,
                "price": bundle.price,
                "quantity": qty,
                "subtotal": bundle.price * qty
            })

    context = {
        "cart": cart,
        "store": store,
        "items": items,
        "show_floating_cart": False,
        "show_navbar": False,
        "simple_navbar": False,
    }

    # -------------------------
    # STORE OPEN CHECK
    # -------------------------
    if not is_store_open_cached(store):
        context["error"] = f"{store.name} is currently closed"
        return render(request, "checkout.html", context)

    # -------------------------
    # SAFE SUBTOTAL (🔥 FIXED)
    # -------------------------
    subtotal = get_cart_details(cart)

    # =========================
    # 🔥 VALIDATE CART AGAIN
    # =========================
    validated_subtotal = get_cart_details(cart)

    if validated_subtotal <= 0:

        request.session["cart"] = {
            "store_id": None,
            "items": {}
        }

        request.session.modified = True

        context["error"] = "Invalid cart"

        return render(request, "checkout.html", context)

    subtotal = validated_subtotal

    # -------------------------
    # UPI ONLY CHECK
    # -------------------------
    upi_only_required = False

    for item_id in cart['items']:

        if item_id.isdigit():
            product = products_map.get(int(item_id))
            if product and product.upi_only:
                upi_only_required = True

        elif item_id.startswith("bundle_"):
            bundle = bundles_map.get(int(item_id.split("_")[1]))
            if bundle:
                for item in bundle.items.all():
                    if item.product.upi_only:
                        upi_only_required = True
                        break

    handling_fee = Decimal(5) if subtotal < 100 else Decimal(9)
    free_delivery_order = False

    customer_phone = request.session.get("customer_phone")

    if customer_phone:

        delivered_orders = Order.objects.filter(
            phone=customer_phone,
            status="DELIVERED"
        ).count()

        next_order_number = delivered_orders + 1

        free_delivery_order = (
            next_order_number == 5
            or next_order_number == 10
        )

    context.update({
        "subtotal": subtotal,
        "handling_fee": handling_fee,
        "upi_only_required": upi_only_required,
        "free_delivery_order": free_delivery_order
    })

    # =========================
    # POST LOGIC
    # =========================
    if request.method == "POST":
        try:
            
            name = request.POST.get("name")
            phone = request.POST.get("phone", "").strip()
            confirm_phone = request.POST.get("confirm_phone") == "on"
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

            try:

                latitude = float(latitude)
                longitude = float(longitude)

            except:

                context["error"] = "Invalid location"

                return render(request, "checkout.html", context)

            # -------------------------
            # DELIVERY CALCULATION
            # -------------------------
            BUS_LAT, BUS_LON = 16.579620, 74.312661
            raw_distance = calculate_distance(latitude, longitude, BUS_LAT, BUS_LON)

            distance = raw_distance if raw_distance <= 1 else 1 + (raw_distance - 1) * 1.55

            if distance > 10:
                context["error"] = "Delivery not available"
                return render(request, "checkout.html", context)

            # -------------------------
            # FREE DELIVERY LOGIC
            # -------------------------

            delivered_orders = Order.objects.filter(
                phone=phone,
                status="DELIVERED"
            ).count()

            # 1st order OR every 5th order
            next_order_number = delivered_orders + 1

            is_free_delivery_order = (
                next_order_number == 5
                or next_order_number == 10
            )

            if is_free_delivery_order:

                delivery_fee = Decimal(0)

            elif subtotal >= 999:

                delivery_fee = Decimal(0)

            else:

                if distance <= 2:
                    delivery_fee = Decimal(15)

                elif distance <= 3:
                    delivery_fee = Decimal(18)

                elif distance <= 4:
                    delivery_fee = Decimal(20)

                elif distance <= 5:
                    delivery_fee = Decimal(23)

                elif distance <= 6:
                    delivery_fee = Decimal(27)

                elif distance <= 7:
                    delivery_fee = Decimal(30)

                else:
                    delivery_fee = Decimal(40)

            # -------------------------
            # COUPON
            # -------------------------

            discount_from_frontend = request.POST.get(
                "discount_amount",
                "0"
            )

            try:
                discount = Decimal(
                    str(discount_from_frontend)
                )
            except:
                discount = Decimal(0)

            if subtotal < 149 and payment == "COD":

                context["error"] = "COD not allowed below ₹149"

                return render(request, "checkout.html", context)

            coupon = None

            if coupon_code:

                try:

                    coupon = Coupon.objects.get(
                        code=coupon_code.strip(),
                        is_active=True
                    )

                    if coupon.used_count >= coupon.usage_limit:

                        context["error"] = "Coupon fully used"

                        return render(request, "checkout.html", context)

                    already_used = CouponUsage.objects.filter(
                        coupon=coupon,
                        phone=phone
                    ).exists()

                    # APPLY DISCOUNT IMMEDIATELY

                    if coupon.discount_type == "PERCENTAGE":

                        discount = (
                            subtotal *
                            Decimal(str(coupon.discount_value))
                        ) / Decimal("100")

                    elif coupon.discount_type == "FIXED":

                        discount = Decimal(
                            str(coupon.discount_value)
                        )

                    # SAFETY
                    if discount > subtotal:
                        discount = subtotal

                    print("COUPON TYPE:", coupon.discount_type)
                    print("COUPON VALUE:", coupon.discount_value)
                    print("DISCOUNT APPLIED:", discount)

                    if already_used:

                        context["error"] = "Coupon already used"

                        return render(request, "checkout.html", context)

                except Coupon.DoesNotExist:

                    context["error"] = "Invalid coupon"

                    return render(request, "checkout.html", context)

            # Prevent over discount
            if discount > subtotal:

                discount = subtotal

            # FINAL TOTAL
            total = (
                subtotal
                + delivery_fee
                + handling_fee
                - discount
            ).quantize(
                Decimal("1"),
                rounding=ROUND_HALF_UP
            )
            print("========== CHECKOUT DEBUG ==========")
            print("COUPON CODE:", coupon_code)
            print("DISCOUNT:", discount)
            print("DELIVERY:", delivery_fee)
            print("FINAL TOTAL:", total)
            print("====================================")

            # ===================================
            # SAVE CHECKOUT LEAD
            # ===================================

            if phone:

                lead, created = CheckoutLead.objects.get_or_create(
                    phone=phone,
                    defaults={
                        "name": name,
                        "address": address,
                        "last_cart_value": total,
                        "last_payment_method": payment,
                        "last_store": store
                    }
                )

                if not created:

                    lead.name = name
                    lead.address = address
                    lead.last_cart_value = total
                    lead.last_payment_method = payment
                    lead.last_store = store
                    lead.checkout_attempts += 1

                    lead.save()

            # Prevent negative total
            if total < 0:
                total = Decimal(0)
            # =========================
            # COD FLOW
            # =========================
            if payment == "COD":

                with transaction.atomic():

                    

                    order = Order.objects.create(
                        store=store,
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
                    request.session["customer_phone"] = phone

                    for item_id, item in cart["items"].items():
                        qty = safe_qty(item.get("quantity", 1))

                        if item_id.isdigit():
                            
                            product = products_map.get(int(item_id))
                            if product:
                                final_price = product.discount_price or product.price
                                OrderItem.objects.create(
                                    order=order,
                                    product=product,
                                    quantity=qty,
                                    #customer price
                                    price=final_price,

                                    # actual store price
                                    original_price=product.price,

                                    # platform discount
                                    discount_amount=(
                                        product.price - final_price
                                    )
                                )

                        elif item_id.startswith("bundle_"):
                            bundle = bundles_map.get(int(item_id.split("_")[1]))
                            if bundle:
                                OrderItem.objects.create(
                                    order=order,

                                    # bundle
                                    bundle=bundle,
                                    bundle_name=bundle.name,

                                    # no product
                                    product=None,

                                    quantity=qty,

                                    # customer paid
                                    price=bundle.price,

                                    # same as selling price
                                    original_price=bundle.price,

                                    # no discount
                                    discount_amount=0
                                )

                request.session["cart"] = {"store_id": None, "items": {}}
                if coupon:

                    CouponUsage.objects.get_or_create(
                        coupon=coupon,
                        phone=phone
                    )

                    coupon.used_count = F("used_count") + 1

                    coupon.save(update_fields=["used_count"])
                return redirect("order_success", order_id=order.id)


            # =========================
            # 🔵 UPI FLOW
            # =========================
            if payment == "UPI":

                import razorpay

                import copy

                # -----------------------------------
                # SAFE JSON DATA
                # -----------------------------------
                def convert_decimals(obj):

                    if isinstance(obj, Decimal):
                        return float(obj)

                    if isinstance(obj, dict):
                        return {
                            k: convert_decimals(v)
                            for k, v in obj.items()
                        }

                    if isinstance(obj, list):
                        return [
                            convert_decimals(i)
                            for i in obj
                        ]

                    return obj


                safe_cart = convert_decimals(
                    copy.deepcopy(cart)
                )

                safe_items = convert_decimals(
                    copy.deepcopy(items)
                )

                # ALWAYS CREATE NEW PENDING ORDER
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

                    cart_data=safe_cart,

                    items_snapshot=safe_items,

                    otp_expiry=timezone.now() + timedelta(minutes=5),
                )

                # SAVE NEW SESSION
                request.session["pending_id"] = pending.id
                request.session.modified = True

                client = razorpay.Client(auth=(
                        settings.RAZORPAY_KEY_ID,
                        settings.RAZORPAY_KEY_SECRET
                    ))

                amount_paise = to_paise(total)
                print("====== PAYMENT DEBUG ======")
                print("SUBTOTAL:", subtotal)
                print("DELIVERY:", delivery_fee)
                print("HANDLING:", handling_fee)
                print("DISCOUNT:", discount)
                print("FINAL TOTAL:", total)
                print("AMOUNT PAISE:", amount_paise)
                print("===========================")

                # 🔥 ALWAYS CREATE NEW ORDER (DO NOT REUSE)
                print("RAZORPAY AMOUNT:", amount_paise)

                razorpay_order = client.order.create({
                    "amount": amount_paise,
                    "currency": "INR",
                    "payment_capture": 1
                })

                razorpay_order_id = razorpay_order["id"]
                pending.razorpay_order_id = razorpay_order_id
                pending.cart_data = safe_cart

                pending.save(
                    update_fields=[
                        "razorpay_order_id",
                        "cart_data"
                    ]
                )

                # optional (just for debugging / reference)
                request.session["razorpay_order_id"] = razorpay_order_id
                request.session["razorpay_amount"] = amount_paise

                logger.info("=========== CHECKOUT DEBUG ===========")
                logger.info(f"TOTAL: {total}")
                logger.info(f"AMOUNT_PAISE: {amount_paise}")
                logger.info(f"RAZORPAY_ORDER_ID: {razorpay_order_id}")
                logger.info(f"PENDING_ID: {pending.id}")
                logger.info("=====================================")
                
                request.session["customer_phone"] = phone
                from django.urls import reverse

                upi_url = reverse("upi_payment")

                import time

                return redirect(
                    f"{upi_url}"
                    f"?amount={amount_paise}"
                    f"&order_id={razorpay_order_id}"
                    f"&display_amount={float(total)}"
                    f"&name={name}"
                    f"&phone={phone}"
                    f"&pending_id={pending.id}"
                    f"&t={int(time.time())}"
                )

            request.session["cart"] = {"store_id": None, "items": {}}

            return redirect("order_success", order_id=order.id)

        except Exception as e:
            logger.error(f"CHECKOUT ERROR: {e}", exc_info=True)
            context["error"] = "Something went wrong"
            return render(request, "checkout.html", context)

    return render(request, "checkout.html", context)

@csrf_exempt
def save_checkout_lead(request):

    if request.method == "POST":

        try:

            data = json.loads(request.body)

            name = data.get("name", "")
            phone = data.get("phone", "").strip()
            address = data.get("address", "")
            payment = data.get("payment", "")
            total = data.get("total", 0)
            store_id = data.get("store_id")

            # VALID PHONE
            if not re.match(r'^[6-9]\d{9}$', phone):

                return JsonResponse({
                    "success": False
                })

            store = None

            if store_id:

                store = Store.objects.filter(
                    id=store_id
                ).first()

            lead, created = CheckoutLead.objects.get_or_create(

                phone=phone,

                defaults={

                    "name": name,
                    "address": address,
                    "last_cart_value": total,
                    "last_payment_method": payment,
                    "last_store": store

                }
            )

            if not created:

                lead.name = name
                lead.address = address
                lead.last_cart_value = total
                lead.last_payment_method = payment
                lead.last_store = store

                lead.checkout_attempts += 1

                lead.save()

            print("✅ AUTO LEAD SAVED:", phone)

            return JsonResponse({
                "success": True
            })

        except Exception as e:

            print("❌ AUTO SAVE ERROR:", e)

            return JsonResponse({
                "success": False
            })

    return JsonResponse({
        "success": False
    })


@csrf_exempt
def razorpay_webhook(request):

    if request.method != "POST":
        return HttpResponse(status=400)

    body = request.body

    received_signature = request.headers.get(
        "X-Razorpay-Signature"
    )

    client = razorpay.Client(
        auth=(
            settings.RAZORPAY_KEY_ID,
            settings.RAZORPAY_KEY_SECRET
        )
    )

    # -----------------------------------
    # VERIFY SIGNATURE
    # -----------------------------------
    try:

        client.utility.verify_webhook_signature(
            body.decode(),
            received_signature,
            settings.RAZORPAY_WEBHOOK_SECRET
        )

    except Exception as e:

        logger.error(f"Webhook verification failed: {e}")

        return HttpResponse(status=400)

    payload = json.loads(body)

    event = payload.get("event")

    # -----------------------------------
    # ONLY SUCCESS PAYMENT
    # -----------------------------------
    if event != "payment.captured":
        return HttpResponse(status=200)

    payment = payload["payload"]["payment"]["entity"]

    razorpay_payment_id = payment["id"]

    razorpay_order_id = payment["order_id"]

    logger.info(f"Webhook received: {razorpay_payment_id}")

    try:

        with transaction.atomic():

            # -----------------------------------
            # FIND PENDING
            # -----------------------------------
            pending = PendingOrder.objects.select_for_update().filter(
                razorpay_order_id=razorpay_order_id
            ).first()

            if not pending:

                logger.warning("Pending order missing")

                return HttpResponse(status=200)

            # -----------------------------------
            # ALREADY COMPLETED
            # -----------------------------------
            if pending.is_completed:

                logger.warning("Pending already completed")

                return HttpResponse(status=200)

            # -----------------------------------
            # DUPLICATE PAYMENT CHECK
            # -----------------------------------
            existing_order = Order.objects.filter(
                payment_id=razorpay_payment_id
            ).first()

            if existing_order:

                logger.warning("Duplicate webhook")

                return HttpResponse(status=200)

            # -----------------------------------
            # CREATE ORDER
            # -----------------------------------
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
                payment_id=razorpay_payment_id,
                status="REQUEST_SUBMITTED"
            )

            # -----------------------------------
            # CREATE ORDER ITEMS
            # -----------------------------------
            cart_data = pending.cart_data

            product_ids = [
                int(i)
                for i in cart_data["items"]
                if i.isdigit()
            ]

            bundle_ids = [
                int(i.split("_")[1])
                for i in cart_data["items"]
                if i.startswith("bundle_")
            ]

            products_map = {
                p.id: p
                for p in Product.objects.filter(
                    id__in=product_ids
                )
            }

            bundles_map = {
                b.id: b
                for b in Bundle.objects.filter(
                    id__in=bundle_ids
                )
            }

            for item_id, item in cart_data["items"].items():

                qty = safe_qty(item.get("quantity", 1))

                # PRODUCT
                if item_id.isdigit():

                    product = products_map.get(int(item_id))

                    if not product:
                        continue

                    final_price = (
                        product.discount_price
                        or product.price
                    )

                    OrderItem.objects.create(
                        order=order,
                        product=product,
                        quantity=qty,
                        price=final_price,
                        original_price=product.price,
                        discount_amount=(
                            product.price - final_price
                        )
                    )

                # BUNDLE
                elif item_id.startswith("bundle_"):

                    bundle = bundles_map.get(
                        int(item_id.split("_")[1])
                    )

                    if not bundle:
                        continue

                    OrderItem.objects.create(
                        order=order,
                        bundle=bundle,
                        bundle_name=bundle.name,
                        quantity=qty,
                        price=bundle.price,
                        original_price=bundle.price,
                        discount_amount=0
                    )

            # -----------------------------------
            # SAFETY CHECK
            # -----------------------------------
            if not order.items.exists():

                logger.error("No valid items")

                order.delete()

                return HttpResponse(status=400)

            # -----------------------------------
            # MARK COMPLETED
            # -----------------------------------
            
            pending.is_completed = True
            pending.is_payment_processed = True

            pending.save(update_fields=[
                "is_completed",
                "is_payment_processed"
            ])

            logger.info(f"Webhook order created: {order.id}")

    except Exception as e:

        logger.error(
            f"WEBHOOK ERROR: {str(e)}",
            exc_info=True
        )

        return HttpResponse(status=500)

    return HttpResponse(status=200)


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

    # ✅ CLEAR CART ALWAYS
    request.session["cart"] = {
        "store_id": None,
        "items": {}
    }

    request.session.modified = True

    order = get_object_or_404(
        Order,
        id=order_id
    )

    return render(
        request,
        "order_success.html",
        {
            "order": order,
            "show_navbar": False,
            "show_floating_cart": False, 'simple_navbar': False,
        }
    )

def order_tracking(request, order_id):
    order = get_object_or_404(Order, id=order_id)
    existing_rating = StoreRating.objects.filter(
        order=order
    ).first()
    return render(request, 'order_tracking.html', {'order': order,
    "show_floating_cart": False, "show_navbar": False, 'simple_navbar': False, "existing_rating": existing_rating,
    })


def my_orders(request):

    phone = request.GET.get('phone', '').strip()

    orders = None

    if phone:
        orders = Order.objects.filter(phone=phone).order_by('-created_at')

    return render(request, 'my_orders.html', {
        'orders': orders,
        'phone': phone,
        'show_navbar': False,
        'simple_navbar': False,
        "show_floating_cart": False
    })


# =====================================================
# SEARCH
# =====================================================

import traceback
import logging

from django.db.models import Q
from django.core.cache import cache
from django.http import HttpResponse

logger = logging.getLogger(__name__)


def search_products(request):

    try:

        query = request.GET.get('q', '').strip()
        highlight_id = request.GET.get("highlight")

        if not query:
            return render(request, 'search_results.html', {
                'query': query,
                'products': [],
                'stores': [],
                "show_floating_cart": True
            })

        store_filter = request.GET.get("store")
        min_price = request.GET.get("min_price")
        max_price = request.GET.get("max_price")
        sort = request.GET.get("sort")

        cache_key = (
            f"search_{query or 'empty'}_"
            f"{store_filter}_{sort}_{min_price}_{max_price}"
        )

        ids = cache.get(cache_key)

        # =====================================================
        # CACHE MISS
        # =====================================================
        if not ids:

            products = Product.objects.select_related('store')\
                .prefetch_related('store__timings')\
                .filter(
                    Q(name__icontains=query) |
                    Q(store__name__icontains=query)
                )

            # =========================
            # FILTERS
            # =========================

            if store_filter:
                products = products.filter(store_id=store_filter)

            if min_price:
                try:
                    products = products.filter(price__gte=float(min_price))
                except:
                    pass

            if max_price:
                try:
                    products = products.filter(price__lte=float(max_price))
                except:
                    pass

            # convert queryset to list for sorting
            products = list(products)

            # =========================
            # SORTING
            # =========================

            if sort == "price_low":
                products.sort(key=lambda x: float(x.price))

            elif sort == "price_high":
                products.sort(key=lambda x: -float(x.price))

            elif sort == "newest":
                products.sort(key=lambda x: -x.id)

            # =========================
            # SEARCH RANKING
            # =========================

            for p in products:

                p.score = 0

                try:
                    if p.name.lower().startswith(query.lower()):
                        p.score += 3

                    elif query.lower() in p.name.lower():
                        p.score += 2

                    if p.store and query.lower() in p.store.name.lower():
                        p.score += 1

                except Exception as e:
                    logger.warning(f"Ranking error: {e}")
                    p.score = 0

            products.sort(key=lambda x: -x.score)

            ids = [p.id for p in products]

            cache.set(cache_key, ids, 120)

        # =====================================================
        # CACHE HIT
        # =====================================================

        products = list(
            Product.objects.select_related('store')
            .prefetch_related('store__timings')
            .filter(id__in=ids)
        )

        # preserve cached order
        products.sort(key=lambda x: ids.index(x.id))

        # =====================================================
        # STORE STATUS
        # =====================================================

        store_status_map = {}

        for p in products:

            try:

                if not p.store:
                    continue

                store_id = p.store.id

                if store_id not in store_status_map:
                    store_status_map[store_id] = is_store_open_cached(p.store)

            except Exception as e:

                logger.warning(
                    f"Store status error for product {p.id}: {e}"
                )

                store_status_map[store_id] = False

        for p in products:

            try:
                p.open_status = store_status_map.get(
                    p.store.id,
                    False
                )

            except Exception as e:

                logger.warning(f"Open status attach error: {e}")

                p.open_status = False

        stores = Store.objects.all()

        for product in products:
            product.available_now = product.is_available_now()

        return render(request, 'search_results.html', {
            'query': query,
            'products': products,
            'stores': stores,
            'selected_store': store_filter,
            'selected_sort': sort,
            'min_price': min_price,
            'max_price': max_price,
            "highlight_id": highlight_id,
            "show_floating_cart": True
        })

    # =====================================================
    # ERROR LOGGING
    # =====================================================

    except Exception as e:

        print("\n" + "="*70)
        print("🚨 SEARCH VIEW ERROR")
        print("="*70)

        print("QUERY:")
        print(request.GET.get("q"))

        print("\nERROR TYPE:")
        print(type(e).__name__)

        print("\nERROR:")
        print(str(e))

        print("\nTRACEBACK:")
        traceback.print_exc()

        print("="*70 + "\n")

        logger.error(
            "SEARCH VIEW ERROR",
            exc_info=True
        )

        return HttpResponse(
            f"""
            <h2>Search Error</h2>
            <p><strong>{type(e).__name__}</strong></p>
            <pre>{str(e)}</pre>
            """,
            status=500
        )

def search_suggestions(request):

    query = request.GET.get('q', '').strip()

    suggestions = []

    if query:

        # =========================
        # PRODUCTS
        # =========================
        products = Product.objects.select_related('store')\
            .filter(name__icontains=query)[:6]

        for product in products:

            suggestions.append({

                'type': 'product',

                'id': product.id,

                'name': product.name,

                'store_id': product.store.id,

                'store_name': product.store.name,

                'image': (
                    product.image.url
                    if product.image else ''
                ),

                'price': str(
                    product.discount_price or product.price
                )

            })

        # =========================
        # STORES
        # =========================
        stores = Store.objects.filter(
            name__icontains=query
        )[:4]

        for store in stores:

            suggestions.append({

                'type': 'store',

                'id': store.id,

                'name': store.name,

                'store_name': store.name,

            })

    return JsonResponse({
        'results': suggestions
    })

# =====================================================
# AJAX DELIVERY CALCULATION
# =====================================================
def calculate_delivery(request):
    latitude = request.GET.get("latitude")
    longitude = request.GET.get("longitude")
    cart = request.session.get('cart', {'items': {}})
    
    subtotal = get_cart_details(cart)

    phone = request.GET.get("phone", "").strip()

    delivered_orders = 0

    if re.match(r'^[6-9]\d{9}$', phone):

        delivered_orders = Order.objects.filter(
            phone=phone,
            status="DELIVERED"
        ).count()

    next_order_number = delivered_orders + 1

    free_delivery = (
        next_order_number == 5
        or next_order_number == 10
    )

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

    BUS_STAND_LAT = 16.579620
    BUS_STAND_LON = 74.312661

    raw_distance = calculate_distance(latitude, longitude, BUS_STAND_LAT, BUS_STAND_LON)

    if raw_distance <= 1:
        distance = raw_distance
    else:
        distance = 1 + (raw_distance - 1) * 1.55

    handling_fee = Decimal(5) if subtotal < 99 else Decimal(9)

    delivery_fee = 15

    if free_delivery:
        delivery_fee = Decimal(0)

    elif subtotal >= 999:
        delivery_fee = Decimal(0)

    else:

        if distance <= 2:
            delivery_fee = Decimal(15)
        elif distance <= 3:
            delivery_fee = Decimal(18)
        elif distance <= 4:
            delivery_fee = Decimal(20)
        elif distance <= 5:
            delivery_fee = Decimal(23)
        elif distance <= 6:
            delivery_fee = Decimal(27)
        elif distance <= 7:
            delivery_fee = Decimal(30)
        else:
            delivery_fee = Decimal(40)


        if delivery_fee > 80:
            delivery_fee = Decimal(80)

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
        "distance": round(distance, 2),
        "free_delivery": free_delivery
    })


import razorpay
import logging
from django.http import HttpResponse
from django.shortcuts import redirect
from django.conf import settings
from django.db import transaction
from decimal import Decimal

logger = logging.getLogger(__name__)

from django.http import JsonResponse
from django.shortcuts import redirect
from django.views.decorators.csrf import csrf_exempt
@csrf_exempt
def payment_success(request):

    pending_id = request.GET.get("pending_id")

    if not pending_id:
        return render(request, "payment_processing.html")

    pending = PendingOrder.objects.filter(
        id=pending_id
    ).first()

    if not pending:
        return render(request, "payment_processing.html")

    # webhook completed?
    if pending.is_completed:

        order = Order.objects.filter(
            phone=pending.phone,
            total=pending.total,
            payment_method="UPI"
        ).order_by("-id").first()

        if order:

            # CLEAR CART
            request.session["cart"] = {
                "store_id": None,
                "items": {}
            }

            request.session.pop("pending_id", None)

            request.session.modified = True

            return redirect(
                "order_success",
                order_id=order.id
            )

    return render(
        request,
        "payment_processing.html"
    )

from django.http import JsonResponse

def check_payment_status(request):

    order_id = request.GET.get("order_id")

    if not order_id:

        return JsonResponse({
            "success": False
        })

    pending = PendingOrder.objects.filter(
        razorpay_order_id=order_id
    ).first()

    if not pending:

        return JsonResponse({
            "success": False
        })

    # webhook completed?
    if pending.is_completed:

        order = Order.objects.filter(
            phone=pending.phone,
            total=pending.total,
            payment_method="UPI"
        ).order_by("-id").first()

        if order:

            request.session["cart"] = {
                "store_id": None,
                "items": {}
            }

            request.session.modified = True

            return JsonResponse({
                "success": True,
                "redirect_url":
                    f"/order-success/{order.id}/"
            })

    return JsonResponse({
        "success": False
    })

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

from django.http import HttpResponseForbidden

def cancel_order(request, order_id):

    order = get_object_or_404(Order, id=order_id)

    # --------------------------------
    # SECURITY CHECK
    # --------------------------------
    customer_phone = request.session.get("customer_phone")

    if not customer_phone:
        return HttpResponseForbidden("Unauthorized")

    if customer_phone != order.phone:
        return HttpResponseForbidden("Unauthorized")

    # --------------------------------
    # ALLOW ONLY EARLY CANCELLATION
    # --------------------------------
    if order.status not in ["REQUEST_SUBMITTED", "ACCEPTED"]:
        return redirect("order_tracking", order_id=order.id)

    # --------------------------------
    # COD FLOW
    # --------------------------------
    if order.payment_method == "COD":

        order.status = "CANCELLED"
        order.save(update_fields=["status"])

        return redirect("order_tracking", order_id=order.id)

    # --------------------------------
    # UPI REFUND FLOW
    # --------------------------------
    if order.payment_method == "UPI":

        if order.is_refunded:
            return redirect("order_tracking", order_id=order.id)

        client = razorpay.Client(auth=(
            settings.RAZORPAY_KEY_ID,
            settings.RAZORPAY_KEY_SECRET
        ))

        refund_amount = to_paise(order.total)

        try:

            refund = client.payment.refund(
                order.payment_id,
                {
                    "amount": refund_amount
                }
            )

            order.status = "CANCELLED"
            order.refund_id = refund["id"]
            order.refund_amount = order.total
            order.is_refunded = True

            order.save(update_fields=[
                "status",
                "refund_id",
                "refund_amount",
                "is_refunded"
            ])

        except Exception as e:

            logger.error(f"Refund failed: {e}")

            return HttpResponse(
                "Refund failed. Contact support."
            )

        return redirect("order_tracking", order_id=order.id)

    return redirect("order_tracking", order_id=order.id)

from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle
from reportlab.lib import colors
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.lib.units import inch
from django.http import HttpResponse
import io


def generate_invoice(request, order_id):
    """
    Concept C — Watermark + PAID stamp invoice.
    Brand: forest green (#2D5A27) + orange (#E8621A).
    Uses canvas-level drawing for full layout control.
    """
    from reportlab.pdfgen import canvas as rl_canvas
    from reportlab.lib.pagesizes import A4
    from reportlab.lib import colors
    from reportlab.lib.colors import HexColor
    from reportlab.lib.units import mm
    from reportlab.pdfbase import pdfmetrics
    from reportlab.pdfbase.ttfonts import TTFont
    import io, os
    from django.conf import settings

    order = get_object_or_404(Order, id=order_id)

    # ── Fonts ──
    font_path = os.path.join(settings.BASE_DIR, "static/fonts/NotoSans-Regular.ttf")
    font_bold_path = os.path.join(settings.BASE_DIR, "static/fonts/NotoSans-Bold.ttf")

    try:
        pdfmetrics.registerFont(TTFont("Noto", font_path))
        pdfmetrics.registerFont(TTFont("Noto-Bold", font_bold_path))
        FONT_REG  = "Noto"
        FONT_BOLD = "Noto-Bold"
    except Exception:
        FONT_REG  = "Helvetica"
        FONT_BOLD = "Helvetica-Bold"

    # ── Brand colours ──
    GREEN_DARK  = HexColor('#1A3A16')
    GREEN_MID   = HexColor('#2D5A27')
    GREEN_LIGHT = HexColor('#EAF2E8')
    ORANGE      = HexColor('#E8621A')
    GREY_TEXT   = HexColor('#9AA899')
    GREY_BORDER = HexColor('#E0E8DF')
    GREY_LIGHT  = HexColor('#D0E4CE')
    OFF_WHITE   = HexColor('#F7F9F6')
    TEXT_DARK   = HexColor('#1A2E19')
    TEXT_MID    = HexColor('#6B7B69')

    W, H   = A4
    margin = 18 * mm
    cw     = W - 2 * margin   # content width

    buffer = io.BytesIO()
    c = rl_canvas.Canvas(buffer, pagesize=A4)
    c.setTitle(f"LOKA Invoice #{order.id}")

    # ─────────────────────────────────────────
    # WATERMARK
    # ─────────────────────────────────────────
    c.saveState()
    c.setFillColor(GREEN_MID)
    c.setFillAlpha(0.032)
    c.setFont(FONT_BOLD, 88)
    c.translate(W / 2, H / 2)
    c.rotate(28)
    c.drawCentredString(0, 0, "LOKA")
    c.restoreState()

    y = H - 18 * mm

    # ─────────────────────────────────────────
    # LOGO MARK  (green rounded square + orange bar)
    # ─────────────────────────────────────────
    ls = 11 * mm   # logo square size
    c.setFillColor(GREEN_MID)
    c.roundRect(margin, y - ls, ls, ls, 2 * mm, fill=1, stroke=0)
    c.setFillColor(colors.white)
    c.setFont(FONT_BOLD, 8)
    c.drawString(margin + ls * 0.17, y - ls * 0.72, "L")
    c.setFillColor(ORANGE)
    c.rect(margin + ls * 0.4, y - ls * 0.52, ls * 0.42, ls * 0.15, fill=1, stroke=0)

    # Brand name
    c.setFillColor(GREEN_MID)
    c.setFont(FONT_BOLD, 18)
    c.drawString(margin + ls + 3 * mm, y - 5.5 * mm, "LOKA")
    c.setFillColor(GREY_TEXT)
    c.setFont(FONT_REG, 7)
    c.drawString(margin + ls + 3 * mm, y - 10.5 * mm, "Loka Marketplace  ·  loka-store.online")

    # Invoice number (top right)
    c.setFillColor(GREY_TEXT)
    c.setFont(FONT_REG, 7)
    c.drawRightString(W - margin, y - 1 * mm, "INVOICE")
    c.setFillColor(TEXT_DARK)
    c.setFont(FONT_BOLD, 16)
    c.drawRightString(W - margin, y - 7 * mm, f"#{order.id}")
    c.setFillColor(GREY_TEXT)
    c.setFont(FONT_REG, 8)
    c.drawRightString(W - margin, y - 12.5 * mm, order.created_at.strftime("%d %b %Y"))

    y -= 18 * mm

    # ─────────────────────────────────────────
    # GRADIENT DIVIDER  (orange → green)
    # ─────────────────────────────────────────
    steps = 80
    seg   = cw / steps
    for i in range(steps):
        t = i / steps
        r = int(0xE8 + (0x2D - 0xE8) * t)
        g = int(0x62 + (0x5A - 0x62) * t)
        b = int(0x1A + (0x27 - 0x1A) * t)
        c.setFillColorRGB(r / 255, g / 255, b / 255)
        c.rect(margin + i * seg, y, seg + 0.6, 2 * mm, fill=1, stroke=0)

    y -= 7 * mm

    # ─────────────────────────────────────────
    # TWO-COLUMN  Bill to / Invoice details
    # ─────────────────────────────────────────
    col_w = cw / 2 - 5 * mm

    def label(x, yy, txt):
        c.setFillColor(GREY_TEXT)
        c.setFont(FONT_REG, 7)
        c.drawString(x, yy, txt.upper())

    def val(x, yy, txt, bold=False):
        c.setFillColor(TEXT_DARK)
        c.setFont(FONT_BOLD if bold else FONT_REG, 9)
        c.drawString(x, yy, txt)

    label(margin, y, "Bill To")
    y -= 5 * mm
    val(margin, y, order.customer_name, bold=True)
    y -= 4.5 * mm
    val(margin, y, str(order.phone))
    y -= 4.5 * mm
    # truncate address so it stays on one line
    addr = str(order.address)[:55]
    val(margin, y, addr)

    # right column
    rx = margin + col_w + 8 * mm
    ry = y + 9 * mm
    label(rx, ry, "Invoice Details")
    ry -= 5 * mm
    val(rx, ry, f"Date: {order.created_at.strftime('%d %b %Y')}")
    ry -= 4.5 * mm
    val(rx, ry, f"Payment: {order.payment_method}")
    ry -= 4.5 * mm
    val(rx, ry, f"Store: {order.store.name}")

    y -= 12 * mm

    # ─────────────────────────────────────────
    # ITEMS TABLE
    # ─────────────────────────────────────────
    col_widths = [cw - 72 * mm, 18 * mm, 27 * mm, 27 * mm]
    headers    = ["Product", "Qty", "Price", "Total"]

    # Table header bar
    hh = 8.5 * mm
    c.setFillColor(GREEN_MID)
    c.roundRect(margin, y - hh, cw, hh, 2 * mm, fill=1, stroke=0)

    hx = margin + 3 * mm
    c.setFillColor(colors.white)
    c.setFont(FONT_BOLD, 7.5)
    for i, h in enumerate(headers):
        if i == 0:
            c.drawString(hx, y - 5.8 * mm, h)
        else:
            c.drawRightString(hx + col_widths[i] - 2 * mm, y - 5.8 * mm, h)
        hx += col_widths[i]

    y -= hh

    # Item rows
    for idx, item in enumerate(order.items.all()):
        rh   = 8.5 * mm
        bg   = OFF_WHITE if idx % 2 == 0 else colors.white
        c.setFillColor(bg)
        c.rect(margin, y - rh, cw, rh, fill=1, stroke=0)

        name = item.product.name if item.product else (item.bundle_name or "Combo")
        name = name[:55]
        price    = float(item.price)
        subtotal = float(item.price * item.quantity)

        ix = margin + 3 * mm
        c.setFillColor(TEXT_DARK)
        c.setFont(FONT_REG, 8.5)
        c.drawString(ix, y - 5.8 * mm, name)
        ix += col_widths[0]
        c.drawRightString(ix + col_widths[1] - 2 * mm, y - 5.8 * mm, str(item.quantity))
        ix += col_widths[1]
        c.drawRightString(ix + col_widths[2] - 2 * mm, y - 5.8 * mm, f"Rs.{price:.0f}")
        ix += col_widths[2]
        c.drawRightString(ix + col_widths[3] - 2 * mm, y - 5.8 * mm, f"Rs.{subtotal:.0f}")

        y -= rh
        c.setStrokeColor(GREY_BORDER)
        c.setLineWidth(0.3)
        c.line(margin, y, margin + cw, y)

    y -= 5 * mm

    # ─────────────────────────────────────────
    # TOTALS BOX
    # ─────────────────────────────────────────
    totals_data = [("Subtotal", float(order.subtotal))]
    if order.delivery_fee > 0:
        totals_data.append(("Delivery", float(order.delivery_fee)))
    if order.handling_fee > 0:
        totals_data.append(("Handling Fee", float(order.handling_fee)))
    if order.discount > 0:
        totals_data.append(("Coupon Discount", -float(order.discount)))
    totals_data.append(("Total", float(order.total)))

    box_h = len(totals_data) * 6.5 * mm + 12 * mm
    c.setFillColor(OFF_WHITE)
    c.roundRect(margin, y - box_h, cw, box_h, 2 * mm, fill=1, stroke=0)

    ty = y - 6.5 * mm
    right_edge = margin + cw - 3 * mm
    label_x    = margin + cw * 0.52

    for label_txt, amount in totals_data[:-1]:
        c.setFillColor(TEXT_MID)
        c.setFont(FONT_REG, 8.5)
        c.drawString(label_x, ty, label_txt)
        prefix = "-Rs." if amount < 0 else "Rs."
        c.drawRightString(right_edge, ty, f"{prefix}{abs(amount):.0f}")
        ty -= 6.5 * mm

    # dashed separator
    c.setStrokeColor(GREY_LIGHT)
    c.setLineWidth(0.5)
    c.setDash(2, 3)
    c.line(label_x, ty + 4 * mm, right_edge, ty + 4 * mm)
    c.setDash()

    # grand total
    c.setFillColor(GREEN_DARK)
    c.setFont(FONT_BOLD, 13)
    c.drawString(label_x, ty, "Total")
    c.drawRightString(right_edge, ty, f"Rs.{float(order.total):.0f}")

    y -= box_h + 6 * mm

    # ─────────────────────────────────────────
    # DELIVERED STAMP  (rotated, right side)
    # ─────────────────────────────────────────
    c.saveState()
    stamp_cx = margin + cw * 0.78
    stamp_cy = y + 14 * mm
    c.translate(stamp_cx, stamp_cy)
    c.rotate(-8)
    c.setStrokeColor(GREEN_MID)
    c.setFillColor(GREEN_LIGHT)
    c.setLineWidth(1.5)
    c.roundRect(-14 * mm, -4 * mm, 28 * mm, 10 * mm, 2 * mm, fill=1, stroke=1)
    c.setFillColor(GREEN_MID)
    c.setFont(FONT_BOLD, 8)
    c.drawCentredString(0, -1 * mm, f"{order.status}  \u2713")
    c.restoreState()

    # refund note if applicable
    if order.is_refunded:
        c.setFillColor(ORANGE)
        c.setFont(FONT_REG, 8)
        c.drawString(margin, y - 2 * mm, f"Refunded: Rs.{float(order.refund_amount):.0f}")

    y -= 10 * mm

    # ─────────────────────────────────────────
    # FOOTER
    # ─────────────────────────────────────────
    footer_h = 18 * mm
    c.setFillColor(GREEN_DARK)
    c.rect(0, 0, W, footer_h, fill=1, stroke=0)

    c.setFillColor(colors.white)
    c.setFont(FONT_BOLD, 8.5)
    c.drawString(margin, 13 * mm, "Thank you for ordering with LOKA!")
    c.setFont(FONT_REG, 7)
    c.setFillColor(HexColor('#A8C9A5'))
    c.drawString(margin, 8.5 * mm, "loka-store.online  ·  आपल्यासाठी, आपल्या लोकांसाठी")

    c.setFillColor(HexColor('#A8C9A5'))
    c.setFont(FONT_REG, 7)
    c.drawRightString(W - margin, 13 * mm, f"Order #{order.id}")
    c.drawRightString(W - margin, 8.5 * mm, order.payment_method)

    # orange accent strip at very bottom
    c.setFillColor(ORANGE)
    c.rect(0, 0, W, 3 * mm, fill=1, stroke=0)

    # ─────────────────────────────────────────
    # BUILD & RETURN
    # ─────────────────────────────────────────
    c.save()
    buffer.seek(0)

    response = HttpResponse(buffer.getvalue(), content_type="application/pdf")
    response["Content-Disposition"] = f'inline; filename="loka-invoice-{order.id}.pdf"'
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
    styles['Title'].fontName = 'Noto'
    styles['Heading2'].fontName = 'Noto'
    styles['Normal'].fontName = 'Noto'

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

        ('FONTNAME', (0,0), (-1,-1), 'Noto'),

        ('BACKGROUND', (0, 0), (-1, 0), colors.lightgrey),

        ('GRID', (0, 0), (-1, -1), 0.5, colors.grey),

        ('ALIGN', (1, 1), (-1, -1), 'CENTER')

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
    styles['Title'].fontName = 'Noto'
    styles['Heading2'].fontName = 'Noto'
    styles['Normal'].fontName = 'Noto'

    elements.append(Paragraph("<b>Store Order Slip</b>", styles['Title']))
    elements.append(Spacer(1, 0.3 * inch))
    elements.append(Paragraph(f"<b>Store:</b> {order.store.name}", styles['Normal']))
    elements.append(Spacer(1, 0.3 * inch))

    data = [["Product", "Qty", "Price"]]

    for item in order.items.all():
        data.append([
            item.product.name if item.product else item.bundle_name,
            str(item.quantity),
            f"₹{item.original_price or item.price}"
        ])

    data.append(["", "Total:", f"₹{order.subtotal}"])

    table = Table(data, colWidths=[3 * inch, 1 * inch, 1 * inch])
    table.setStyle(TableStyle([

        ('FONTNAME', (0,0), (-1,-1), 'Noto'),

        ('BACKGROUND', (0, 0), (-1, 0), colors.lightgrey),

        ('GRID', (0, 0), (-1, -1), 0.5, colors.grey),

        ('ALIGN', (1, 1), (-1, -1), 'CENTER')

    ]))
    elements.append(table)

    doc.build(elements)
    buffer.seek(0)

    return HttpResponse(buffer, content_type='application/pdf')

from django.http import JsonResponse
from .models import Order

from django.db.models import Q

from django.http import JsonResponse

def check_free_delivery(request):

    phone = request.GET.get("phone", "").strip()

    if not re.match(r'^[6-9]\d{9}$', phone):
        return JsonResponse({
            "next_is_free": False,
            "hide_message": True
        })

    delivered_orders = Order.objects.filter(
        phone=phone,
        status="DELIVERED"
    ).count()

    next_order = delivered_orders + 1

    # 5th or 10th order
    if next_order in [5, 10]:
        return JsonResponse({
            "next_is_free": True,
            "order_count": delivered_orders
        })

    # Stop showing messages after 10 delivered orders
    if delivered_orders >= 10:
        return JsonResponse({
            "next_is_free": False,
            "hide_message": True
        })

    return JsonResponse({
        "next_is_free": False,
        "order_count": delivered_orders
    })

def combo_detail(request, combo_id):

    combo = Bundle.objects.get(id=combo_id)

    if not is_store_open_cached(combo.store):
        return JsonResponse({
            "error": "Store is currently closed"
        }, status=400)

    items = []

    for item in combo.items.all():

        items.append({
            "name": item.bundle_name,
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


import traceback
import logging

logger = logging.getLogger(__name__)

def admin_dashboard(request):

    try:

        # ====================================
        # YOUR EXISTING CODE
        # ====================================

        total_revenue = (
            Order.objects.filter(status="DELIVERED")
            .aggregate(total=Sum("total"))["total"] or 0
        )

        total_orders = Order.objects.count()

        todays_orders = Order.objects.filter(
            created_at__date=timezone.now().date()
        ).count()

        avg_order_value = (
            total_revenue / total_orders
            if total_orders > 0 else 0
        )

        repeat_customers = (
            Order.objects.values("phone")
            .annotate(c=Count("id"))
            .filter(c__gt=1)
            .count()
        )

        delivered = Order.objects.filter(
            status="DELIVERED"
        ).count()

        delivery_success = (
            round((delivered / total_orders) * 100, 2)
            if total_orders else 0
        )

        cod_orders = Order.objects.filter(
            payment_method="COD"
        ).count()

        upi_orders = Order.objects.filter(
            payment_method="UPI"
        ).count()

        # ====================================
        # PLATFORM COMMISSION
        # ====================================

        platform_commission = Decimal(0)

        delivered_orders = Order.objects.filter(
            status="DELIVERED"
        ).select_related("store")

        for order in delivered_orders:

            store_percent = (
                order.store.commission_percent or 0
            )

            commission = (
                Decimal(order.subtotal)
                * Decimal(store_percent)
            ) / Decimal(100)

            platform_commission += commission

        # ====================================
        # TOP PRODUCTS
        # ====================================

        top_products = (
            OrderItem.objects
            .values("product__name")
            .annotate(total_qty=Sum("quantity"))
            .order_by("-total_qty")[:10]
        )

        # ====================================
        # TOP STORES
        # ====================================

        top_stores = (
            Order.objects
            .values("store__name")
            .annotate(revenue=Sum("total"))
            .order_by("-revenue")[:10]
        )

        # ====================================
        # CHART DATA
        # ====================================

        last_7_days = []

        labels = []
        revenues = []

        for i in range(6, -1, -1):

            day = timezone.now().date() - timedelta(days=i)

            revenue = (
                Order.objects.filter(
                    created_at__date=day,
                    status="DELIVERED"
                ).aggregate(
                    total=Sum("total")
                )["total"] or 0
            )

            labels.append(day.strftime("%d %b"))
            revenues.append(float(revenue))

        # ====================================
        # HOURLY ORDERS
        # ====================================

        hourly_orders = []

        for hour in range(10, 22):

            count = Order.objects.filter(
                created_at__hour=hour
            ).count()

            hourly_orders.append(count)

        # ====================================
        # TEMPLATE RENDER
        # ====================================

        return render(request, "admin_dashboard.html", {

            "total_revenue": total_revenue,
            "platform_commission": round(platform_commission, 2),
            "total_orders": total_orders,
            "todays_orders": todays_orders,
            "avg_order_value": avg_order_value,
            "repeat_customers": repeat_customers,
            "delivery_success": delivery_success,

            "cod_orders": cod_orders,
            "upi_orders": upi_orders,

            "top_products": top_products,
            "top_stores": top_stores,

            "labels": json.dumps(labels),
            "revenues": json.dumps(revenues),
            "hourly_orders": json.dumps(hourly_orders),

        })

    except Exception as e:

        print("\n" + "="*80)
        print("🚨 ADMIN DASHBOARD ERROR")
        print("="*80)

        print("\nERROR TYPE:")
        print(type(e).__name__)

        print("\nERROR MESSAGE:")
        print(str(e))

        print("\nFULL TRACEBACK:")
        traceback.print_exc()

        print("\nDATABASE QUERIES:")
        try:
            for q in connection.queries[-10:]:
                print(q)
        except:
            print("Could not fetch queries")

        print("="*80 + "\n")

        logger.error(
            "ADMIN DASHBOARD ERROR",
            exc_info=True
        )

        return HttpResponse(

            f"""
            <h1>Dashboard Error</h1>

            <h3>{type(e).__name__}</h3>

            <pre>{str(e)}</pre>
            """,

            status=500
        )
    
from .models import Coupon
from .models import CouponUsage

@transaction.atomic
def apply_coupon(request):

    code = request.GET.get("code", "").strip().upper()
    phone = request.GET.get("phone", "").strip()

    if not code:
        return JsonResponse({
            "success": False,
            "message": "Enter coupon code"
        })

    try:

        # -----------------------------------
        # LOCK COUPON ROW
        # -----------------------------------
        coupon = Coupon.objects.select_for_update().get(
            code=code,
            is_active=True
        )

    except Coupon.DoesNotExist:

        return JsonResponse({
            "success": False,
            "message": "Invalid coupon"
        })

    # -----------------------------------
    # CART
    # -----------------------------------
    try:

        cart = request.session.get("cart") or {
            "items": {}
        }

        subtotal = get_cart_details(cart)

    except:

        subtotal = Decimal(0)

    now = timezone.now()

    # -----------------------------------
    # DATE VALIDATION
    # -----------------------------------
    if now < coupon.valid_from or now > coupon.valid_to:

        return JsonResponse({
            "success": False,
            "message": "Coupon expired"
        })

    # -----------------------------------
    # MIN ORDER
    # -----------------------------------
    if subtotal < coupon.min_order_value:

        return JsonResponse({
            "success": False,
            "message": f"Minimum order ₹{coupon.min_order_value} required"
        })

    # -----------------------------------
    # USAGE LIMIT
    # -----------------------------------
    if coupon.used_count >= coupon.usage_limit:

        return JsonResponse({
            "success": False,
            "message": "Coupon fully used"
        })

    # -----------------------------------
    # PHONE REUSE CHECK
    # -----------------------------------
    if phone:

        already_used = CouponUsage.objects.filter(
            coupon=coupon,
            phone=phone
        ).exists()

        if already_used:

            return JsonResponse({
                "success": False,
                "message": "Coupon already used"
            })

    # -----------------------------------
    # CALCULATE DISCOUNT
    # -----------------------------------
    if coupon.discount_type == "PERCENT":

        discount = (
            subtotal * coupon.discount_value / 100
        )

        if coupon.max_discount:

            discount = min(
                discount,
                coupon.max_discount
            )

    else:

        discount = coupon.discount_value

    # -----------------------------------
    # SAVE TEMP SESSION
    # -----------------------------------
    request.session["applied_coupon"] = {
        "code": coupon.code,
        "discount": str(discount)
    }

    request.session.modified = True

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

        from decimal import Decimal

        original_sales = Decimal(0)
        discount_sales = Decimal(0)

        for order in orders:

            for item in order.items.all():

                qty = item.quantity

                original_price = (
                    item.original_price
                    if item.original_price
                    else item.price
                )

                customer_price = item.price

                original_sales += (
                    Decimal(original_price) * qty
                )

                discount_sales += (
                    (Decimal(original_price) - Decimal(customer_price)) * qty
                )

        commission_percent = (
            Decimal(store.commission_percent) / Decimal(100)
        )

        platform_commission = (
            original_sales * commission_percent
        )

        platform_earn = (
            platform_commission - discount_sales
        )

        store_payout = (
            original_sales - platform_commission
        )

        loss = discount_sales

        store_data.append({
            "store": store,
            "orders": order_count,
            "sales": round(sales,2),
            "original_sales": original_sales,
            "discount_sales": discount_sales,
            "loss": loss,
            "platform_earn": platform_earn,
            "payout": store_payout,
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

    context = {
        "razorpay_key": settings.RAZORPAY_KEY_ID,
        "amount": request.GET.get("amount"),
        "razorpay_order_id": request.GET.get("order_id"),
        "display_amount": request.GET.get("display_amount"),
        "customer_name": request.GET.get("name"),
        "phone": request.GET.get("phone"),
        "pending_id": request.GET.get("pending_id"),
        "show_floating_cart": False,
        "show_navbar": False,
        "simple_navbar": False,

    }

    print("UPI PAYMENT PENDING ID:",
          context["pending_id"])

    return render(
        request,
        "upi_payment.html",
        context
    )

def download_app(request):
    return render(request, "download_app.html", {
        "show_floating_cart": False,
        "simple_navbar": True
    })

@require_POST
def submit_rating(request, order_id):

    try:
        order = Order.objects.get(id=order_id)

    except Order.DoesNotExist:

        return JsonResponse({
            "success": False,
            "message": "Order not found"
        })

    # -----------------------------------
    # SECURITY 1
    # ONLY DELIVERED ORDER
    # -----------------------------------

    if order.status != "DELIVERED":

        return JsonResponse({
            "success": False,
            "message": "Rating allowed only after delivery"
        })

    # -----------------------------------
    # SECURITY 2
    # SAME CUSTOMER ONLY
    # -----------------------------------

    customer_phone = request.session.get("customer_phone")

    if not customer_phone:

        return JsonResponse({
            "success": False,
            "message": "Login required"
        })

    if customer_phone != order.phone:

        return JsonResponse({
            "success": False,
            "message": "Unauthorized"
        })

    # -----------------------------------
    # SECURITY 3
    # ONE RATING PER ORDER
    # -----------------------------------

    if StoreRating.objects.filter(order=order).exists():

        return JsonResponse({
            "success": False,
            "message": "Rating already submitted"
        })

    # -----------------------------------
    # GET DATA
    # -----------------------------------

    rating = request.POST.get("rating")
    comment = request.POST.get("comment", "")

    if not rating:

        return JsonResponse({
            "success": False,
            "message": "Rating required"
        })

    rating = int(rating)

    if rating < 1 or rating > 5:

        return JsonResponse({
            "success": False,
            "message": "Invalid rating"
        })

    # -----------------------------------
    # CREATE RATING
    # -----------------------------------

    StoreRating.objects.create(
        order=order,
        store=order.store,
        customer_phone=customer_phone,
        rating=rating,
        comment=comment
    )

    # -----------------------------------
    # UPDATE STORE AVERAGE
    # -----------------------------------

    ratings = StoreRating.objects.filter(
        store=order.store
    )

    avg_rating = ratings.aggregate(
        Avg("rating")
    )["rating__avg"] or 0

    total_ratings = ratings.count()

    order.store.average_rating = round(avg_rating, 1)
    order.store.total_ratings = total_ratings

    order.store.save(update_fields=[
        "average_rating",
        "total_ratings"
    ])

    return JsonResponse({
        "success": True
    })


from rest_framework.decorators import api_view
from rest_framework.response import Response

from .models import DeviceToken

@api_view(["POST"])
def save_fcm_token(request):

    token = request.data.get("token")

    phone = request.data.get("phone")

    if not token:

        return Response({
            "error": "Token missing"
        }, status=400)

    DeviceToken.objects.update_or_create(

        token=token,

        defaults={
            "phone": phone
        }
    )

    return Response({
        "message": "Token saved"
    })


from django.contrib.admin.views.decorators import staff_member_required

@staff_member_required
def pending_orders_dashboard(request):

    pending_orders = PendingOrder.objects.order_by(
        "-created_at"
    )

    return render(
        request,
        "pending_orders_dashboard.html",
        {
            "pending_orders": pending_orders
        }
    )


from django.http import JsonResponse

def save_checkout_lead(request):

    if request.method == "POST":

        try:

            name = request.POST.get("name")
            phone = request.POST.get("phone", "").strip()
            address = request.POST.get("address")
            payment = request.POST.get("payment")

            total = request.POST.get("total", 0)

            store_id = request.POST.get("store_id")

            # VALID PHONE ONLY
            if not re.match(r'^[6-9]\d{9}$', phone):

                return JsonResponse({
                    "success": False
                })

            store = None

            if store_id:
                store = Store.objects.filter(
                    id=store_id
                ).first()

            lead, created = CheckoutLead.objects.get_or_create(

                phone=phone,

                defaults={
                    "name": name,
                    "address": address,
                    "last_cart_value": total,
                    "last_payment_method": payment,
                    "last_store": store
                }
            )

            if not created:

                lead.name = name
                lead.address = address
                lead.last_cart_value = total
                lead.last_payment_method = payment
                lead.last_store = store

                lead.checkout_attempts += 1

                lead.save()

            return JsonResponse({
                "success": True
            })

        except Exception as e:

            print("SAVE CHECKOUT LEAD ERROR:", e)
            return JsonResponse({
                "success": False
            })

    return JsonResponse({
        "success": False
    })

def debug_view(view_func):

    def wrapper(request, *args, **kwargs):

        try:

            return view_func(request, *args, **kwargs)

        except Exception as e:

            print("\n🔥🔥🔥 SERVER ERROR 🔥🔥🔥")
            print("VIEW:", view_func.__name__)
            print(traceback.format_exc())

            logger.error(
                f"ERROR IN {view_func.__name__}",
                exc_info=True
            )

            return HttpResponse(
                f"""
                <h1>SERVER ERROR</h1>
                <pre>
{traceback.format_exc()}
                </pre>
                """,
                status=500
            )

    return wrapper

@staff_member_required
@debug_view
def income_expense_dashboard(request):

    orders = Order.objects.exclude(
        status="CANCELLED"
    )

    expenses = Expense.objects.all().order_by(
        "-created_at"
    )

    # =========================
    # DATE FILTER
    # =========================

    start_date = request.GET.get("start_date")
    end_date = request.GET.get("end_date")

    if start_date and end_date:

        orders = orders.filter(
            created_at__date__range=[
                start_date,
                end_date
            ]
        )

        expenses = expenses.filter(
            created_at__date__range=[
                start_date,
                end_date
            ]
        )

    # =========================
    # TOTALS
    # =========================

    total_sales = sum(
        o.subtotal for o in orders
    )

    total_delivery_fee = sum(
        o.delivery_fee for o in orders
    )

    total_handling_fee = sum(
        o.handling_fee for o in orders
    )

    total_commission = 0

    for order in orders:

        if order.store:

            total_commission += (
                order.subtotal *
                order.store.commission_percent
            ) / 100

    total_expense = sum(
        e.amount for e in expenses
    )

    total_earned = (
        total_delivery_fee +
        total_handling_fee +
        total_commission
    )

    remaining = (
        total_earned -
        total_expense
    )

    # =========================
    # ADD EXPENSE
    # =========================

    if request.method == "POST":

        reason = request.POST.get("reason")
        amount = request.POST.get("amount")
        payment_method = request.POST.get(
            "payment_method"
        )

        notes = request.POST.get("notes")

        Expense.objects.create(

            reason=reason,
            amount=amount,
            payment_method=payment_method,
            notes=notes

        )

        return redirect(
            "income_expense_dashboard"
        )

    return render(
        request,
        "income_expense_dashboard.html",
        {

            "total_sales": total_sales,
            "total_delivery_fee": total_delivery_fee,
            "total_handling_fee": total_handling_fee,
            "total_commission": total_commission,
            "total_expense": total_expense,
            "total_earned": total_earned,
            "remaining": remaining,
            "expenses": expenses,
            "start_date": start_date,
            "end_date": end_date

        }
    )

from django.db.models import Sum
from django.db.models import Count
from reportlab.platypus import (
    SimpleDocTemplate,
    Paragraph,
    Spacer,
    Table,
    TableStyle
)
from reportlab.lib import colors
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.lib.pagesizes import letter
from io import BytesIO

def store_orders_dashboard(request):

    stores = Store.objects.all()

    store_id = request.GET.get("store")
    start_date = request.GET.get("start_date")
    end_date = request.GET.get("end_date")

    orders = Order.objects.filter(
        status="DELIVERED"
    )

    selected_store = None

    if store_id:

        orders = orders.filter(
            store_id=store_id
        )

        selected_store = Store.objects.filter(
            id=store_id
        ).first()

    if start_date:

        orders = orders.filter(
            created_at__date__gte=start_date
        )

    if end_date:

        orders = orders.filter(
            created_at__date__lte=end_date
        )

    total_orders = orders.count()

    total_sales = (
        orders.aggregate(
            total=Sum("subtotal")
        )["total"]
        or 0
    )

    commission_percent = 0

    if selected_store:
        commission_percent = (
            selected_store.commission_percent
        )

    platform_fee = (
        total_sales * commission_percent
    ) / 100 if commission_percent else 0

    store_income = total_sales - platform_fee

    all_orders = []

    serial = 1

    for order in orders.order_by("accepted_at"):

        items = []

        for item in order.items.all():

            items.append(
                f"{item.display_name} x {item.quantity}"
            )

        all_orders.append({
            "serial": serial,
            "date": order.accepted_at,
            "items": ", ".join(items),
            "subtotal": order.subtotal
        })

        serial += 1

    return render(
        request,
        "store_orders_dashboard.html",
        {
            "stores": stores,
            "selected_store": selected_store,
            "start_date": start_date,
            "end_date": end_date,
            "total_orders": total_orders,
            "total_sales": total_sales,
            "commission_percent": commission_percent,
            "platform_fee": platform_fee,
            "store_income": store_income,
            "orders": all_orders
        }
    )

from io import BytesIO

from django.http import HttpResponse
from django.shortcuts import get_object_or_404

from django.db.models import Sum
from django.utils.timezone import localtime

from reportlab.platypus import (
    SimpleDocTemplate,
    Paragraph,
    Spacer,
    Table,
    TableStyle
)

from reportlab.lib import colors
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.lib.pagesizes import A4
from reportlab.platypus.flowables import KeepTogether

def store_orders_pdf(request):

    store_id = request.GET.get("store")
    start_date = request.GET.get("start_date")
    end_date = request.GET.get("end_date")

    orders = Order.objects.filter(
        status="DELIVERED"
    ).prefetch_related(
        "items",
        "items__product"
    )

    selected_store = None

    if store_id:

        orders = orders.filter(
            store_id=store_id
        )

        selected_store = Store.objects.filter(
            id=store_id
        ).first()

    if start_date:

        orders = orders.filter(
            created_at__date__gte=start_date
        )

    if end_date:

        orders = orders.filter(
            created_at__date__lte=end_date
        )

    orders = orders.order_by("accepted_at")

    # =====================================
    # KPI
    # =====================================

    total_orders = orders.count()

    total_sales = (
        orders.aggregate(
            total=Sum("subtotal")
        )["total"]
        or 0
    )

    commission_percent = 0

    if selected_store:

        commission_percent = (
            selected_store.commission_percent
        )

    platform_fee = (
        total_sales * commission_percent
    ) / 100 if commission_percent else 0

    store_income = total_sales - platform_fee

    # =====================================
    # PDF SETUP
    # =====================================

    buffer = BytesIO()

    doc = SimpleDocTemplate(
        buffer,
        pagesize=A4,
        rightMargin=20,
        leftMargin=20,
        topMargin=20,
        bottomMargin=20
    )

    styles = getSampleStyleSheet()

    # Marathi Font
    styles["Normal"].fontName = "Noto"
    styles["Heading1"].fontName = "Noto"

    elements = []

    # =====================================
    # TITLE
    # =====================================

    elements.append(

        Paragraph(
            "Store Orders Report",
            styles["Heading1"]
        )

    )

    elements.append(
        Spacer(1, 15)
    )

    # =====================================
    # STORE + DATE
    # =====================================

    store_name = (
        selected_store.name
        if selected_store
        else "All Stores"
    )

    date_range = (
        f"{start_date or '-'} to {end_date or '-'}"
    )

    elements.append(

        Paragraph(
            f"<b>Store:</b> {store_name}",
            styles["Normal"]
        )

    )

    elements.append(

        Paragraph(
            f"<b>Date Range:</b> {date_range}",
            styles["Normal"]
        )

    )

    elements.append(
        Spacer(1, 15)
    )

    # =====================================
    # KPI SECTION
    # =====================================

    elements.append(
        Paragraph(
            f"<b>Total Orders:</b> {total_orders}",
            styles["Normal"]
        )
    )

    elements.append(
        Paragraph(
            f"<b>Total Sales:</b> ₹{round(total_sales, 2)}",
            styles["Normal"]
        )
    )

    elements.append(
        Paragraph(
            f"<b>Commission:</b> {commission_percent}%",
            styles["Normal"]
        )
    )

    elements.append(
        Paragraph(
            f"<b>Platform Fee:</b> ₹{round(platform_fee, 2)}",
            styles["Normal"]
        )
    )

    elements.append(
        Paragraph(
            f"<b>Store Income:</b> ₹{round(store_income, 2)}",
            styles["Normal"]
        )
    )

    elements.append(
        Spacer(1, 20)
    )

    # =====================================
    # TABLE
    # =====================================

    data = [[

        Paragraph("<b>S.No</b>", styles["Normal"]),

        Paragraph("<b>Accepted Time</b>", styles["Normal"]),

        Paragraph("<b>Items</b>", styles["Normal"]),

        Paragraph("<b>Subtotal</b>", styles["Normal"])

    ]]

    serial = 1
    subtotal_total = 0

    for order in orders:

        items_text = []

        for item in order.items.all():

            item_name = item.display_name

            items_text.append(
                f"{item_name} x {item.quantity}"
            )

        items_joined = ", ".join(items_text)

        accepted_time = "-"

        if order.accepted_at:

            accepted_time = localtime(
                order.accepted_at
            ).strftime(
                "%d-%m-%Y %I:%M %p"
            )

        data.append([

            Paragraph(
                str(serial),
                styles["Normal"]
            ),

            Paragraph(
                accepted_time,
                styles["Normal"]
            ),

            Paragraph(
                items_joined,
                styles["Normal"]
            ),

            Paragraph(
                f"₹{order.subtotal}",
                styles["Normal"]
            )

        ])

        subtotal_total += order.subtotal

        serial += 1

    # =====================================
    # TOTAL ROW
    # =====================================

    data.append([

        "",
        "",
        Paragraph(
            "<b>TOTAL</b>",
            styles["Normal"]
        ),

        Paragraph(
            f"<b>₹{round(subtotal_total, 2)}</b>",
            styles["Normal"]
        )

    ])

    # =====================================
    # TABLE WIDTHS
    # =====================================

    table = Table(

        data,

        colWidths=[
            45,
            120,
            280,
            80
        ],

        repeatRows=1

    )

    table.setStyle(TableStyle([

        # FONT
        ('FONTNAME', (0,0), (-1,-1), 'Noto'),

        # HEADER
        ('BACKGROUND', (0,0), (-1,0), colors.lightgrey),

        # GRID
        ('GRID', (0,0), (-1,-1), 0.5, colors.black),

        # ALIGN
        ('VALIGN', (0,0), (-1,-1), 'TOP'),

        ('ALIGN', (0,0), (0,-1), 'CENTER'),

        ('ALIGN', (3,0), (3,-1), 'CENTER'),

        # FONT SIZE
        ('FONTSIZE', (0,0), (-1,-1), 9),

        # PADDING
        ('TOPPADDING', (0,0), (-1,-1), 6),

        ('BOTTOMPADDING', (0,0), (-1,-1), 6),

    ]))

    elements.append(
        KeepTogether(table)
    )

    # =====================================
    # BUILD PDF
    # =====================================

    doc.build(elements)

    pdf = buffer.getvalue()

    buffer.close()

    response = HttpResponse(
        pdf,
        content_type="application/pdf"
    )

    response[
        "Content-Disposition"
    ] = (
        'attachment; '
        'filename="store_orders_report.pdf"'
    )

    return response

from django.db.models import (
    Count,
    Sum,
    Min,
    Max
)
from django.db.models.functions import TruncDate
from django.contrib.admin.views.decorators import staff_member_required

from django.http import JsonResponse
from django.utils import timezone


@staff_member_required
def orders_dashboard(request):

    start_date = request.GET.get("start")
    end_date = request.GET.get("end")

    orders = Order.objects.filter(
        status="DELIVERED"
    )

    if start_date:
        orders = orders.filter(
            created_at__date__gte=start_date
        )

    if end_date:
        orders = orders.filter(
            created_at__date__lte=end_date
        )

    # ==================================
    # KPI
    # ==================================

    total_orders = orders.count()

    total_sales = (
        orders.aggregate(
            total=Sum("total")
        )["total"]
        or 0
    )

    aov = round(
        total_sales / total_orders,
        2
    ) if total_orders else 0

    unique_customers = (
        orders.values("phone")
        .distinct()
        .count()
    )

    # ==================================
    # CUSTOMER FREQUENCY
    # ==================================

    customer_orders = (
        orders
        .values(
            "phone",
            "customer_name"
        )
        .annotate(
            order_count=Count("id")
        )
    )

    one_time = customer_orders.filter(
        order_count=1
    ).count()

    two_time = customer_orders.filter(
        order_count=2
    ).count()

    three_time = customer_orders.filter(
        order_count=3
    ).count()

    five_plus = customer_orders.filter(
        order_count__gte=5
    ).count()

    # ==================================
    # FIRST ORDER DATE
    # ==================================

    first_orders = {
        item["phone"]: item["first_order"].date()
        for item in (
            Order.objects
            .filter(status="DELIVERED")
            .values("phone")
            .annotate(
                first_order=Min("created_at")
            )
        )
    }

    # ==================================
    # DAILY SUMMARY
    # ==================================

    table_rows = []

    daily_stats = (
        orders
        .annotate(
            day=TruncDate("created_at")
        )
        .values("day")
        .annotate(
            total_orders=Count("id"),
            total_sales=Sum("total"),
            delivery_fee=Sum("delivery_fee"),
            handling_fee=Sum("handling_fee")
        )
        .order_by("-day")
    )

    for row in daily_stats:

        day = row["day"]

        day_orders = orders.filter(
            created_at__date=day
        )

        phones = list(
            day_orders
            .values_list(
                "phone",
                flat=True
            )
            .distinct()
        )

        new_customers = sum(
            1
            for phone in phones
            if first_orders.get(phone) == day
        )

        repeat_customers = (
            len(phones)
            - new_customers
        )

        sales = row["total_sales"] or 0

        table_rows.append({
            "date": day,
            "orders": row["total_orders"],
            "sales": sales,
            "aov": round(
                sales / row["total_orders"],
                2
            ) if row["total_orders"] else 0,
            "new_customers": new_customers,
            "repeat_customers": repeat_customers,
            "delivery_fee": row["delivery_fee"] or 0,
            "handling_fee": row["handling_fee"] or 0,
        })

    # ==================================
    # RFM ANALYSIS
    # ==================================

    customer_rfm = []

    customers = (
        orders
        .values(
            "phone",
            "customer_name"
        )
        .annotate(
            frequency=Count("id"),
            monetary=Sum("total"),
            last_order=Max("created_at")
        )
        .order_by("-monetary")
    )

    today = timezone.now().date()

    for customer in customers:

        recency = (
            today
            - customer["last_order"].date()
        ).days

        frequency = customer["frequency"]

        monetary = customer["monetary"]

        if recency <= 15 and frequency >= 5:
            segment = "Champion"

        elif frequency >= 3:
            segment = "Loyal"

        elif recency <= 30:
            segment = "New"

        elif recency > 90:
            segment = "Lost"

        else:
            segment = "At Risk"

        customer_rfm.append({
            "name": customer["customer_name"],
            "phone": customer["phone"],
            "recency": recency,
            "frequency": frequency,
            "monetary": monetary,
            "segment": segment,
        })
    
    champion_count = sum(
        1 for c in customer_rfm
        if c["segment"] == "Champion"
    )

    loyal_count = sum(
        1 for c in customer_rfm
        if c["segment"] == "Loyal"
    )

    new_count = sum(
        1 for c in customer_rfm
        if c["segment"] == "New"
    )

    atrisk_count = sum(
        1 for c in customer_rfm
        if c["segment"] == "At Risk"
    )

    lost_count = sum(
        1 for c in customer_rfm
        if c["segment"] == "Lost"
    )

    segment_filter = request.GET.get("rfm_segment", "")
    if segment_filter:
        customer_rfm = [
            c for c in customer_rfm
            if c["segment"] == segment_filter
        ]

    context = {
        "total_orders": total_orders,
        "total_sales": total_sales,
        "aov": aov,
        "unique_customers": unique_customers,

        "one_time": one_time,
        "two_time": two_time,
        "three_time": three_time,
        "five_plus": five_plus,

        "table_rows": table_rows,
        "customer_rfm": customer_rfm,
        "selected_segment": segment_filter,

        "start_date": start_date,
        "end_date": end_date,
        "show_navbar": False,
        "champion_count": champion_count,
        "loyal_count": loyal_count,
        "new_count": new_count,
        "atrisk_count": atrisk_count,
        "lost_count": lost_count,
    }

    return render(
        request,
        "orders_dashboard.html",
        context
    )


@staff_member_required
def orders_dashboard_customers(request):

    segment = request.GET.get("segment")
    

    customers = (
        Order.objects
        .filter(
            status="DELIVERED"
        )
        .values(
            "customer_name",
            "phone"
        )
        .annotate(
            orders_count=Count("id"),
            total_spend=Sum("total")
        )
        .order_by("-orders_count")
    )

    if segment == "one":
        customers = customers.filter(
            orders_count=1
        )

    elif segment == "two":
        customers = customers.filter(
            orders_count=2
        )

    elif segment == "three":
        customers = customers.filter(
            orders_count=3
        )

    elif segment == "five":
        customers = customers.filter(
            orders_count__gte=5
        )

    return JsonResponse(
        list(customers),
        safe=False
    )