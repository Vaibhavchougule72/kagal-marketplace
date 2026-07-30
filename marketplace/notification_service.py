from datetime import timedelta

from django.db import transaction
from django.db.models import Count, Max
from django.utils import timezone

from .firebase import send_bulk_push_notifications
from .models import (
    DeviceToken,
    NotificationCampaign,
    Order,
)


# =====================================================
# AUDIENCE HELPERS
# =====================================================

def get_all_customers():
    phones = (
        Order.objects
        .values_list("phone", flat=True)
        .distinct()
    )

    return DeviceToken.objects.filter(phone__in=phones)


def get_new_customers():
    phones = (
        Order.objects
        .filter(status="DELIVERED")
        .values("phone")
        .annotate(total=Count("id"))
        .filter(total=1)
        .values_list("phone", flat=True)
    )

    return DeviceToken.objects.filter(phone__in=phones)


def get_repeat_customers():
    phones = (
        Order.objects
        .filter(status="DELIVERED")
        .values("phone")
        .annotate(total=Count("id"))
        .filter(total__gte=2)
        .values_list("phone", flat=True)
    )

    return DeviceToken.objects.filter(phone__in=phones)


def get_inactive_customers():
    cutoff = timezone.now() - timedelta(days=30)

    phones = (
        Order.objects
        .filter(status="DELIVERED")
        .values("phone")
        .annotate(last_order=Max("created_at"))
        .filter(last_order__lt=cutoff)
        .values_list("phone", flat=True)
    )

    return DeviceToken.objects.filter(phone__in=phones)


def get_phone_customer(phone):
    return DeviceToken.objects.filter(phone=phone)


def get_recipients(audience, phone=None):

    audience_map = {
        "all": get_all_customers,
        "new": get_new_customers,
        "repeat": get_repeat_customers,
        "inactive": get_inactive_customers,
    }

    if audience == "phone":
        return get_phone_customer(phone)

    func = audience_map.get(audience)

    if func:
        return func()

    return DeviceToken.objects.none()


# =====================================================
# CAMPAIGN HELPERS
# =====================================================

def create_campaign(**kwargs):
    return NotificationCampaign.objects.create(**kwargs)


def delete_campaign(campaign):
    campaign.delete()


def duplicate_campaign(campaign):

    campaign.pk = None
    campaign.created_at = None

    campaign.successful = 0
    campaign.failed = 0
    campaign.total_recipients = 0

    campaign.status = "completed"

    campaign.save()

    return campaign


# =====================================================
# SEND NOTIFICATIONS
# =====================================================

def send_bulk_notifications(
    title,
    message,
    audience,
    phone=None,
    high_priority=False,
    save_history=True,
    created_by=None,
):
    """
    Sends notifications to the selected audience.
    Returns campaign statistics.
    """

    recipients = get_recipients(audience, phone)

    tokens = list(
        set(
            recipients.values_list(
                "token",
                flat=True,
            )
        )
    )

    campaign = None

    if save_history:
        campaign = create_campaign(
            title=title,
            message=message,
            audience=audience,
            phone=phone,
            high_priority=high_priority,
            save_history=True,
            status="sending",
            total_recipients=len(tokens),
            created_by=created_by,
        )

    # Nothing to send
    if not tokens:

        if campaign:
            campaign.status = "completed"
            campaign.save(update_fields=["status"])

        return {
            "campaign_id": campaign.id if campaign else None,
            "total": 0,
            "successful": 0,
            "failed": 0,
        }

    # Send notifications using Firebase
    result = send_bulk_push_notifications(
        tokens=tokens,
        title=title,
        body=message,
        high_priority=high_priority,
    )

    # Remove invalid tokens
    invalid_tokens = result.get("invalid_tokens", [])

    if invalid_tokens:
        DeviceToken.objects.filter(
            token__in=invalid_tokens
        ).delete()

    success = result["success"]
    failed = result["failed"]

    if campaign:
        with transaction.atomic():

            campaign.successful = success
            campaign.failed = failed

            campaign.status = (
                "completed"
                if success > 0
                else "failed"
            )

            campaign.save(
                update_fields=[
                    "successful",
                    "failed",
                    "status",
                ]
            )

    return {
        "campaign_id": campaign.id if campaign else None,
        "total": len(tokens),
        "successful": success,
        "failed": failed,
    }