from django.urls import path
from . import views
from django.views.generic import TemplateView
from django.conf.urls.i18n import set_language

urlpatterns = [
    path('', views.home, name='home'),
    

    path('stores/', views.all_stores, name='all_stores'),
    path('store/<int:store_id>/', views.store_detail, name='store_detail'),

    path('category/<int:category_id>/', views.category_detail, name='category_detail'),
    path('category/<int:category_id>/stores/', views.category_stores, name='category_stores'),
    path('category/<int:category_id>/products/', views.category_products, name='category_products'),
    path('cart/', views.view_cart, name='view_cart'),
    path('add-to-cart/<int:product_id>/', views.add_to_cart, name='add_to_cart'),
    path('decrease-cart/<str:product_id>/', views.decrease_cart, name='decrease_cart'),
    path('remove-from-cart/<str:product_id>/', views.remove_from_cart, name='remove_from_cart'),
    path('checkout/', views.checkout, name='checkout'),
    path('order-success/<int:order_id>/', views.order_success, name='order_success'),
    path('order/<int:order_id>/tracking/', views.order_tracking, name='order_tracking'),
    path('my-orders/', views.my_orders, name='my_orders'),
    path('search/', views.search_products, name='search_products'),
    path('search-suggestions/', views.search_suggestions, name='search_suggestions'),
    path("calculate-delivery/", views.calculate_delivery, name="calculate_delivery"),
    #path('verify-otp/<int:pending_id>/', views.verify_otp, name='verify_otp'),
    #path('resend-otp/<int:pending_id>/', views.resend_otp, name='resend_otp'),
    #path("upi_payment/", views.upi_payment, name="upi_payment"),
    path("payment-success/", views.payment_success, name="payment_success"),
    path("cancel-order/<int:order_id>/", views.cancel_order, name="cancel_order"),
    path('invoice/<int:order_id>/', views.generate_invoice, name='generate_invoice'),
    path("faqs/", TemplateView.as_view(template_name="faqs.html"), name="faqs"),
    path("return-policy/", TemplateView.as_view(template_name="return_policy.html"), name="return_policy"),
    path("delivery-info/", TemplateView.as_view(template_name="delivery_info.html"), name="delivery_info"),
    path("check-free-delivery/", views.check_free_delivery, name="check_free_delivery"),
    path("add-bundle/<int:bundle_id>/", views.add_bundle_to_cart, name="add_bundle"),
    path(
        "combo/<int:combo_id>/",
        views.combo_detail,
        name="combo_detail"
    ),
    #path(
    #    "send-delivery-otp/<int:order_id>/",
    #    views.send_delivery_otp,
    #    name="send_delivery_otp"
    #),
    path("admin-dashboard/", views.admin_dashboard, name="admin_dashboard"),
    path("apply-coupon/", views.apply_coupon, name="apply_coupon"),
    path("test-cache/", views.test_cache, name="test_cache"),
    path('set-language/', set_language, name='set_language'),
    path(
        "delivery-dashboard/",
        views.delivery_dashboard,
        name="delivery_dashboard"
    ),
    path("razorpay-webhook/", views.razorpay_webhook),
    path("store-dashboard/", views.store_dashboard, name="store_dashboard"),
    path('privacy-policy/', views.privacy_policy, name='privacy_policy'),
    path("rider-dashboard/", views.rider_dashboard, name="rider_dashboard"),
    path(
        "rider/update-status/<int:order_id>/<str:new_status>/",
        views.rider_update_status,
        name="rider_update_status"
    ),
    path(
        "rider/location/<int:order_id>/",
        views.update_rider_location,
        name="update_rider_location"
    ),
]


