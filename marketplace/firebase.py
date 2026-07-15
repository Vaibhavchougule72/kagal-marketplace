import os
import json
import firebase_admin

from firebase_admin import credentials
from firebase_admin import messaging


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

            print("✅ Firebase initialized successfully")

    except Exception as e:

        print(
            "❌ Firebase initialization failed:",
            str(e)
        )

else:

    print("❌ FIREBASE_CREDENTIALS missing")


# =====================================================
# SEND PUSH NOTIFICATION
# =====================================================

def send_push_notification(
    token,
    title,
    body
):

    if not token:
        raise ValueError("FCM token is empty")

    message = messaging.Message(

        # Notification payload
        notification=messaging.Notification(
            title=str(title),
            body=str(body),
        ),

        # Data payload
        data={
            "title": str(title),
            "body": str(body),
        },

        # Android-specific settings
        android=messaging.AndroidConfig(

            priority="high",

            notification=messaging.AndroidNotification(
                channel_id="LOKA_ORDER_UPDATES_V2",
                sound="default",
                priority="high",
            ),
        ),

        token=token,
    )

    try:

        response = messaging.send(message)

        print(
            "✅ Push notification sent:",
            response
        )

        return response

    except Exception as e:

        print(
            "❌ Push notification failed:",
            str(e)
        )

        raise