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
    """
    Require LOKA customer login for customer-facing pages.
    """

    EXEMPT_PATHS = [
        "/login/",
        "/send-login-otp/",
        "/verify-login-otp/",
        "/verify-login-otp-submit/",
        "/register/",
        "/logout/",
        "/resend-login-otp/",

        # Django/system paths
        "/admin/",
        "/static/",
        "/media/",
        "/.well-known/",

        # Payment webhook must remain publicly accessible
        "/razorpay-webhook/",
    ]

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):

        path = request.path

        # Allow login/authentication/system paths
        if any(
            path.startswith(exempt)
            for exempt in self.EXEMPT_PATHS
        ):
            return self.get_response(request)

        # Check LOKA customer session
        customer_id = request.session.get(
            "customer_id"
        )

        # Customer is not logged in
        if not customer_id:
            return redirect("customer_login")

        # Customer is logged in
        return self.get_response(request)