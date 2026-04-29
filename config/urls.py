# config/urls.py

from django.conf import settings
from django.conf.urls.static import static
from django.http import JsonResponse
from django.urls import path, include
from django.contrib import admin


def assetlinks(request):
    return JsonResponse([
        {
            "relation": [
                "delegate_permission/common.handle_all_urls"
            ],
            "target": {
                "namespace": "android_app",
                "package_name": "com.lokamarketplace.app",
                "sha256_cert_fingerprints": [
                    "CB:04:E9:84:4E:27:42:50:AC:D3:D2:D9:D5:DA:9F:F9:8A:12:A5:6E:37:2B:C3:8D:C0:7B:30:DA:83:2E:65:EE"
                ]
            }
        }
    ], safe=False)


urlpatterns = [
    path("admin/", admin.site.urls),

    path(
        ".well-known/assetlinks.json",
        assetlinks
    ),

    path("", include("marketplace.urls")),
]


if settings.DEBUG:
    urlpatterns += static(
        settings.MEDIA_URL,
        document_root=settings.MEDIA_ROOT
    )