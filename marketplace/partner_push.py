from django.contrib.staticfiles import finders
from django.http import HttpResponse, Http404


def firebase_messaging_service_worker(request):

    worker_path = finders.find("firebase-messaging-sw.js")

    if not worker_path:
        raise Http404("Firebase service worker not found")

    with open(worker_path, "r", encoding="utf-8") as file:
        worker_content = file.read()

    response = HttpResponse(
        worker_content,
        content_type="application/javascript"
    )

    # Allow the worker to control the entire website
    response["Service-Worker-Allowed"] = "/"

    # Avoid serving an outdated worker
    response["Cache-Control"] = "no-cache"

    return response