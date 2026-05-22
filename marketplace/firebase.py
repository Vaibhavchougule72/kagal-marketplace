import os
import json
import firebase_admin

from firebase_admin import credentials
from firebase_admin import messaging

firebase_json = os.getenv("FIREBASE_CREDENTIALS")

if firebase_json:

    cred_dict = json.loads(firebase_json)

    if not firebase_admin._apps:

        cred = credentials.Certificate(cred_dict)

        firebase_admin.initialize_app(cred)


def send_push_notification(
    token,
    title,
    body
):

    message = messaging.Message(

        notification=messaging.Notification(
            title=title,
            body=body,
        ),

        token=token,
    )

    response = messaging.send(message)

    return response