import requests
import os

def send_sms(phone, message):

    url = "https://www.fast2sms.com/dev/bulkV2"

    payload = {
        "sender_id": "FSTSMS",
        "message": message,
        "language": "english",
        "route": "q",  # transactional
        "numbers": phone
    }

    headers = {
        "authorization": "nkfLSNdqHIXW5U6uJteboBVGpFsxOc8ryZTE320KjwPl7aA4v1JAXPqmpIHC9e0axfTBn5oyGOEkdFRN",
        "Content-Type": "application/json"
    }

    try:
        response = requests.post(url, json=payload, headers=headers)
        return response.json()

    except Exception as e:
        print("SMS Error:", e)
        return None

