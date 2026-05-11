from django.db.models.signals import (
    pre_save,
    post_save,
    post_delete
)

from django.dispatch import receiver
from django.core.cache import cache

from .models import (
    Order,
    Product,
    Store,
    Bundle,
    StoreTiming,
    Banner
)

# =====================================================
# ORDER STATUS NOTIFICATION
# =====================================================

@receiver(pre_save, sender=Order)
def order_status_changed(sender, instance, **kwargs):

    if not instance.id:
        return

    try:
        old_order = Order.objects.get(id=instance.id)

    except Order.DoesNotExist:
        return

    if old_order.status != instance.status:

        phone = instance.phone
        order_id = instance.id

        if instance.status == "ACCEPTED":
            message = f"Order #{order_id} has been accepted."

        elif instance.status == "IN_PROGRESS":
            message = f"Your order #{order_id} is being prepared."

        elif instance.status == "OUT_FOR_DELIVERY":
            message = f"Order #{order_id} is out for delivery."

        elif instance.status == "DELIVERED":
            message = f"Order #{order_id} delivered successfully."

        elif instance.status == "CANCELLED":
            message = f"Order #{order_id} has been cancelled."

        else:
            message = f"Order #{order_id} status updated."

        print("NOTIFICATION →", phone, message)


# =====================================================
# PRODUCT CACHE CLEAR
# =====================================================

@receiver([post_save, post_delete], sender=Product)
def invalidate_product_cache(sender, instance, **kwargs):

    cache.delete("home_featured_ids")

    cache.delete(f"store_{instance.store.id}")

    cache.delete(f"store_open_{instance.store.id}")

    # optional
    cache.delete("home_combos")


# =====================================================
# BUNDLE CACHE CLEAR
# =====================================================

@receiver([post_save, post_delete], sender=Bundle)
def invalidate_bundle_cache(sender, instance, **kwargs):

    cache.delete("home_combos")

    cache.delete(f"store_{instance.store.id}")


# =====================================================
# STORE CACHE CLEAR
# =====================================================

@receiver([post_save, post_delete], sender=Store)
def invalidate_store_cache(sender, instance, **kwargs):

    cache.delete(f"store_{instance.id}")

    cache.delete(f"store_open_{instance.id}")

    cache.delete("home_featured_ids")

    cache.delete("home_combos")


# =====================================================
# STORE TIMING CACHE CLEAR
# =====================================================

@receiver([post_save, post_delete], sender=StoreTiming)
def invalidate_store_timing_cache(sender, instance, **kwargs):

    cache.delete(f"store_open_{instance.store.id}")

    cache.delete("home_featured_ids")

    cache.delete("home_combos")


# =====================================================
# BANNER CACHE CLEAR
# =====================================================

@receiver([post_save, post_delete], sender=Banner)
def invalidate_banner_cache(sender, instance, **kwargs):

    cache.delete("home_banners")