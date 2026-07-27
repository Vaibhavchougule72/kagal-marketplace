from datetime import timedelta

from django.db.models import Count, Sum, Max
from django.utils import timezone

from .models import (
    Order,
    DeviceToken,
    NotificationCampaign,
)

def total_customers():

    return (
        Order.objects
        .values("phone")
        .distinct()
        .count()
    )

def active_devices():

    return DeviceToken.objects.count()

def new_customers():

    return (
        Order.objects
        .filter(status="DELIVERED")
        .values("phone")
        .annotate(total=Count("id"))
        .filter(total=1)
        .count()
    )

def repeat_customers():

    return (
        Order.objects
        .filter(status="DELIVERED")
        .values("phone")
        .annotate(total=Count("id"))
        .filter(total__gte=2)
        .count()
    )

def inactive_customers():

    cutoff = timezone.now() - timedelta(days=30)

    return (
        Order.objects
        .filter(status="DELIVERED")
        .values("phone")
        .annotate(last_order=Max("created_at"))
        .filter(last_order__lt=cutoff)
        .count()
    )

def total_campaigns():

    return NotificationCampaign.objects.count()


def todays_campaigns():

    today = timezone.localdate()

    return NotificationCampaign.objects.filter(
        created_at__date=today
    ).count()

def total_notifications_sent():

    return (
        NotificationCampaign.objects.aggregate(
            total=Sum("successful")
        )["total"] or 0
    )

def total_notifications_failed():

    return (
        NotificationCampaign.objects.aggregate(
            total=Sum("failed")
        )["total"] or 0
    )

def success_rate():

    sent = total_notifications_sent()

    failed = total_notifications_failed()

    total = sent + failed

    if total == 0:
        return 0

    return round((sent / total) * 100, 1)

def recent_campaigns(limit=10):

    return NotificationCampaign.objects.order_by(
        "-created_at"
    )[:limit]

def dashboard_statistics():

    return {

        "total_customers": total_customers(),

        "active_devices": active_devices(),

        "new_customers": new_customers(),

        "repeat_customers": repeat_customers(),

        "inactive_customers": inactive_customers(),

        "total_campaigns": total_campaigns(),

        "todays_campaigns": todays_campaigns(),

        "notifications_sent": total_notifications_sent(),

        "notifications_failed": total_notifications_failed(),

        "success_rate": success_rate(),

        "recent_campaigns": recent_campaigns()

    }

