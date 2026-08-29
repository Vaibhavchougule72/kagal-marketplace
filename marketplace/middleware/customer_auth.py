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
        "/admin/",
        "/static/",
        "/media/",
        "/.well-known/",
        "/razorpay-webhook/",
    ]

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):

        path = request.path

        # Allow authentication and system paths
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