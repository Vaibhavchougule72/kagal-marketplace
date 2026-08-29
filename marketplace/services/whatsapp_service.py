import requests
from django.conf import settings


def send_login_otp(phone, otp):
    """
    Send LOKA login OTP through FAST2SMS WhatsApp API.
    """

    # WhatsApp API expects country code.
    # Our database/session uses 10-digit Indian numbers.
    phone = str(phone).strip()

    if phone.startswith("+91"):
        phone = phone[1:]

    elif phone.startswith("91") and len(phone) == 12:
        pass

    elif len(phone) == 10:
        phone = "91" + phone

    url = (
        f"https://www.fast2sms.com/dev/whatsapp/"
        f"{settings.FAST2SMS_WHATSAPP_API_VERSION}/"
        f"{settings.FAST2SMS_WHATSAPP_PHONE_NUMBER_ID}/messages"
    )

    headers = {
        "Authorization": settings.FAST2SMS_API_KEY,
        "Content-Type": "application/json",
    }

    payload = {
        "messaging_product": "whatsapp",
        "recipient_type": "individual",
        "to": phone,
        "type": "template",
        "template": {
            "name": settings.FAST2SMS_WHATSAPP_OTP_TEMPLATE,
            "language": {
                "code": settings.FAST2SMS_WHATSAPP_OTP_LANGUAGE,
            },
            "components": [
                {
                    "type": "body",
                    "parameters": [
                        {
                            "type": "text",
                            "text": str(otp),
                        }
                    ],
                },
                {
                    "type": "button",
                    "sub_type": "url",
                    "index": "0",
                    "parameters": [
                        {
                            "type": "text",
                            "text": str(otp),
                        }
                    ],
                },
            ],
        },
    }

    try:
        response = requests.post(
            url,
            headers=headers,
            json=payload,
            timeout=15,
        )

        print("FAST2SMS STATUS:", response.status_code)
        print("FAST2SMS RESPONSE:", response.text)

        return response

    except requests.RequestException as error:
        print("FAST2SMS ERROR:", error)
        return None