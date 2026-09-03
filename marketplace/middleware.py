from django.utils import translation

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