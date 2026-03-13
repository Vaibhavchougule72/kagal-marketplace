from django.db.models.signals import pre_save
from django.dispatch import receiver
from .models import Order


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

from django.db.models.signals import post_save, post_delete
from django.core.cache import cache

from .models import Product, Store, Bundle


@receiver(post_save, sender=Product)
@receiver(post_delete, sender=Product)
def clear_product_cache(sender, instance, **kwargs):

    cache.delete("home_page")

    cache.delete(f"store_{instance.store.id}")


@receiver(post_save, sender=Bundle)
@receiver(post_delete, sender=Bundle)
def clear_bundle_cache(sender, instance, **kwargs):

    cache.delete("home_page")

    cache.delete(f"store_{instance.store.id}")