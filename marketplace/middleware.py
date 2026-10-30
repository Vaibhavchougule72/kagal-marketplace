from django.utils import translation
import uuid
from datetime import timedelta

from django.utils import timezone
from .models import CustomerVisit

class ForceMarathiMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        if not request.session.get('django_language'):
            translation.activate('mr')
            request.session['django_language'] = 'mr'
        else:
            translation.activate(request.session['django_language'])

        request.LANGUAGE_CODE = translation.get_language()
        return self.get_response(request)
    
class PermissionsPolicyMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        response = self.get_response(request)
        response["Permissions-Policy"] = "geolocation=(), camera=(), microphone=()"
        return response


from django.shortcuts import redirect


class CustomerAuthenticationMiddleware:

    EXEMPT_PATHS = [
        "/login/",
        "/send-login-otp/",
        "/verify-login-otp/",
        "/verify-login-otp-submit/",
        "/register/",
        "/logout/",
        "/resend-login-otp/",
        "/save-fcm-token/",
        "/link-logged-in-fcm-token/",
        "/admin/",
        "/static/",
        "/media/",
        "/.well-known/",
        "/razorpay/webhook/",
        "/check-payment-status/",
        "/upi_payment/",
        "/payment-success/",
        "/partner/",
        "/save-partner-fcm-token/",
    ]

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):

        path = request.path

        if any(path.startswith(path_prefix)
               for path_prefix in self.EXEMPT_PATHS):
            return self.get_response(request)

        customer_id = request.session.get("customer_id")

        if not customer_id:
            return redirect("customer_login")

        return self.get_response(request)


class CustomerNoCacheMiddleware:

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):

        response = self.get_response(request)

        response["Cache-Control"] = (
            "no-store, no-cache, must-revalidate, max-age=0"
        )
        response["Pragma"] = "no-cache"
        response["Expires"] = "0"

        return response

class CustomerVisitTrackingMiddleware:

    EXEMPT_PATHS = [
        "/admin/",
        "/static/",
        "/media/",
        "/api/",
        "/save-fcm-token/",
        "/link-logged-in-fcm-token/",
        "/service-worker.js",
        "/favicon.ico",
        "/robots.txt",
    ]

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):

        response = self.get_response(request)

        # Track only successful HTML page requests
        if request.method != "GET":
            return response

        if response.status_code != 200:
            return response

        if not response.get("Content-Type", "").startswith("text/html"):
            return response

        if any(
            request.path.startswith(prefix)
            for prefix in self.EXEMPT_PATHS
        ):
            return response

        # Track only logged-in customers
        customer_id = request.session.get("customer_id")

        if not customer_id:
            return response

        now = timezone.now()

        # Get existing visit token
        token_value = request.session.get("customer_visit_token")

        try:
            token = uuid.UUID(str(token_value))
        except (ValueError, TypeError, AttributeError):
            token = None

        visit = None

        if token:
            visit = CustomerVisit.objects.filter(
                session_token=token,
                customer_id=customer_id
            ).first()

        # Start a new visit if no previous visit exists
        # or the customer was inactive for more than 30 minutes
        if (
            visit is None
            or now - visit.last_seen_at > timedelta(minutes=30)
        ):
            token = uuid.uuid4()

            CustomerVisit.objects.create(
                customer_id=customer_id,
                session_token=token,
                platform="WEBSITE",
                started_at=now,
                last_seen_at=now,
            )

            request.session["customer_visit_token"] = str(token)

        else:
            visit.last_seen_at = now
            visit.save(update_fields=["last_seen_at"])

        return response