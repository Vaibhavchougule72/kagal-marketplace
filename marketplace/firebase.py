import json
import logging
import os

import firebase_admin
from firebase_admin import credentials, messaging


logger = logging.getLogger(__name__)


# =====================================================
# FIREBASE INITIALIZATION
# =====================================================

firebase_json = os.getenv("FIREBASE_CREDENTIALS")

if firebase_json:
    try:
        cred_dict = json.loads(firebase_json)

        if not firebase_admin._apps:
            cred = credentials.Certificate(cred_dict)
            firebase_admin.initialize_app(cred)
            logger.info("Firebase initialized successfully.")

    except Exception as e:
        logger.exception("Firebase initialization failed: %s", e)

else:
    logger.warning("FIREBASE_CREDENTIALS environment variable not found.")


# =====================================================
# COMMON HELPERS
# =====================================================

def _android_config(high_priority=False):
    """
    Common Android configuration used by all notifications.
    """

    priority = "high" if high_priority else "normal"

    return messaging.AndroidConfig(
        priority=priority,
        notification=messaging.AndroidNotification(
            channel_id="LOKA_ORDER_UPDATES_V2",
            sound="default",
            priority=priority,
        ),
    )


def _chunk_list(items, size=500):
    """
    Firebase allows max 500 tokens per multicast request.
    """

    for i in range(0, len(items), size):
        yield items[i:i + size]


# =====================================================
# SINGLE PUSH NOTIFICATION
# =====================================================

def send_push_notification(
    token,
    title,
    body,
    high_priority=True,
    data=None,
):
    """
    Send notification to a single device.
    """

    if not token:
        raise ValueError("FCM token is empty")

    message = messaging.Message(
        notification=messaging.Notification(
            title=str(title),
            body=str(body),
        ),

        data={
            "title": str(title),
            "body": str(body),
            **(data or {}),
        },

        android=_android_config(high_priority),

        token=token,
    )

    try:

        response = messaging.send(message)

        logger.info(
            "Push notification sent: %s",
            response,
        )

        return response

    except Exception as e:

        logger.exception(
            "Push notification failed: %s",
            e,
        )

        raise


# =====================================================
# BULK PUSH NOTIFICATIONS
# =====================================================

def send_bulk_push_notifications(
    tokens,
    title,
    body,
    high_priority=False,
    data=None,
):
    """
    Send notifications to multiple devices.

    Returns:
    {
        "success": int,
        "failed": int,
        "invalid_tokens": []
    }
    """

    tokens = list(set(filter(None, tokens)))

    if not tokens:
        return {
            "success": 0,
            "failed": 0,
            "invalid_tokens": [],
        }

    success = 0
    failed = 0

    invalid_tokens = []

    notification = messaging.Notification(
        title=str(title),
        body=str(body),
    )

    android = _android_config(high_priority)

    for batch in _chunk_list(tokens, 500):

        multicast = messaging.MulticastMessage(

            tokens=batch,

            notification=notification,

            android=android,

            data={
                "title": str(title),
                "body": str(body),
                **(data or {}),
            },
        )

        try:

            response = messaging.send_each_for_multicast(
                multicast
            )

            success += response.success_count

            failed += response.failure_count

            for token, result in zip(
                batch,
                response.responses,
            ):

                if result.success:
                    continue

                exception = result.exception

                logger.warning(
                    "Failed token %s : %s",
                    token,
                    exception,
                )

                if isinstance(
                    exception,
                    messaging.UnregisteredError,
                ):
                    invalid_tokens.append(token)

        except Exception as e:

            logger.exception(
                "Bulk notification batch failed: %s",
                e,
            )

            failed += len(batch)

    return {
        "success": success,
        "failed": failed,
        "invalid_tokens": invalid_tokens,
    }