from django.db import transaction

from .models import (
    DeliveryPartnerProfile,
    RiderAssignmentState,
    RiderOrderOffer,
)
from .models import Order
from .models import RiderDeviceToken
from .firebase import send_rider_new_order_notification
from datetime import timedelta
from django.utils import timezone

def create_next_rider_offer(order):
    """
    Select the next eligible rider using round-robin logic
    and create an order offer for that rider.
    """

    with transaction.atomic():

        # Lock the order to prevent simultaneous dispatch
        order = (
            Order.objects
            .select_for_update()
            .get(pk=order.pk)
        )

        # Stop if the order is already assigned or closed
        if (
            order.assigned_delivery_id
            or order.status != "REQUEST_SUBMITTED"
        ):
            return None

        # Do not create another offer while one is pending
        if RiderOrderOffer.objects.filter(
            order=order,
            status="PENDING"
        ).exists():
            return None

        # Lock the round-robin cursor
        cursor, _ = RiderAssignmentState.objects.get_or_create(
            pk=1
        )

        cursor = (
            RiderAssignmentState.objects
            .select_for_update()
            .get(pk=1)
        )

        # Riders who have already received an offer for this order
        already_offered = RiderOrderOffer.objects.filter(
            order=order
        ).values_list("rider_id", flat=True)

        # Find eligible riders
        riders = (
            DeliveryPartnerProfile.objects
            .filter(
                is_active=True,
                is_available=True
            )
            .exclude(user_id__in=already_offered)
            .select_related("user")
            .order_by("user_id")
        )

        if not riders.exists():
            return None

        # Select the next rider after the previous rider
        next_rider = riders.filter(
            user_id__gt=(
                cursor.last_assigned_rider_id or 0
            )
        ).first()

        # If no rider is found, start from the beginning
        if next_rider is None:
            next_rider = riders.first()

        # Create the offer
        offer = RiderOrderOffer.objects.create(
            order=order,
            rider=next_rider.user,
            status="PENDING"
        )

        # Update the round-robin cursor
        cursor.last_assigned_rider = next_rider.user
        cursor.save(update_fields=["last_assigned_rider", "updated_at"])

        return offer

def notify_rider_new_order(offer):
    """
    Send a new-order notification to all active devices
    registered by the selected rider.
    """

    tokens = RiderDeviceToken.objects.filter(
        user=offer.rider,
        is_active=True
    )

    if not tokens.exists():
        return 0

    sent_count = 0

    for device in tokens:
        try:
            send_rider_new_order_notification(
                token=device.token,
                order=offer.order,
                offer=offer
            )

            sent_count += 1

        except Exception:
            continue

    return sent_count


def dispatch_order_to_next_rider(order):
    """
    Offer an order to the next eligible rider.
    If notification delivery fails, move to the next rider.
    """

    while True:

        offer = create_next_rider_offer(order)

        # No more eligible riders
        if offer is None:
            return None

        sent_count = notify_rider_new_order(offer)

        # If notification was sent successfully
        if sent_count > 0:

            now = timezone.now()

            offer.notification_count = 1
            offer.first_notified_at = now
            offer.last_notified_at = now
            offer.next_notification_at = now + timedelta(minutes=1)

            offer.save(
                update_fields=[
                    "notification_count",
                    "first_notified_at",
                    "last_notified_at",
                    "next_notification_at",
                ]
            )

            # Schedule the first reminder after 1 minute
            from .tasks import process_rider_offer_reminder

            process_rider_offer_reminder.apply_async(
                args=[offer.id],
                countdown=60,
            )

            return offer

        # No notification could be delivered: escalate this offer
        offer.status = "ESCALATED"
        offer.escalated_at = timezone.now()
        offer.save(
            update_fields=["status", "escalated_at"]
        )